from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, status

from src.helpdesk.contact_token import (
    ContactAccess,
    conversation_url,
    create_contact_token,
)
from src.helpdesk.enums import (
    HelpdeskErrorCode,
    HelpdeskNotificationType,
    HelpdeskUsageMetric,
    MessageAuthorType,
    TicketChannel,
    TicketStatus,
)
from src.helpdesk.models.contact import Contact
from src.helpdesk.models.support_site import SupportSite
from src.helpdesk.models.ticket import Ticket
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.schemas.widget import (
    WidgetAccessLinkIn,
    WidgetConfigOut,
    WidgetMessageIn,
    WidgetMessageOut,
    WidgetTicketCreatedOut,
    WidgetTicketDetailOut,
    WidgetTicketIn,
    WidgetTicketListOut,
    WidgetTicketOut,
)
from src.helpdesk.services.agent_notifications import notify_agents
from src.platform.billing.dependencies import require_within_limit, track_usage
from src.platform.core.exceptions import (
    ClientException,
    NotAuthenticatedException,
    NotFoundException,
)
from src.platform.services.base import BaseService
from src.platform.services.mailer import send_email


class WidgetService(BaseService):
    """Public, unauthenticated entry point for customers using the widget.

    Every call resolves the support site from its slug and scopes the product
    repositories to that site's organization. Ticket access is further limited
    by the contact token presented (see `src.helpdesk.contact_token`).
    """

    def __init__(self, repos: Annotated[HelpdeskRepositoryManager, Depends()]) -> None:
        super().__init__(repos)
        self.helpdesk = repos
        self.sites = repos.support_site
        self.contacts = repos.contact
        self.tickets = repos.ticket
        self.messages = repos.ticket_message

    async def get_config(self, slug: str, *, ai_configured: bool) -> WidgetConfigOut:
        site = await self._site(slug)
        return WidgetConfigOut(
            organization_name=await self.sites.get_organization_name(site),
            brand_color=site.brand_color,
            greeting=site.greeting,
            help_center_enabled=site.help_center_enabled,
            ai_answers_enabled=ai_configured and site.help_center_enabled,
        )

    async def create_ticket(
        self, slug: str, schema_in: WidgetTicketIn, schedule_task: Callable[..., Any]
    ) -> WidgetTicketCreatedOut:
        site = await self._site(slug)
        organization_id = site.organization_id
        await require_within_limit(
            self.repos, organization_id, HelpdeskUsageMetric.TICKETS_PER_MONTH
        )

        contact = await self.contacts.get_by_email(schema_in.email)
        if contact is None:
            contact = await self.contacts.create(
                name=schema_in.name, email=schema_in.email, locale=schema_in.locale
            )
        ticket = await self.tickets.create(
            number=await self.tickets.next_number(),
            subject=schema_in.subject,
            channel=TicketChannel.WIDGET,
            contact_id=contact.id,
            last_message_at=datetime.now(UTC),
        )
        message = await self.messages.create(
            ticket_id=ticket.id,
            author_type=MessageAuthorType.CONTACT,
            author_contact_id=contact.id,
            body=schema_in.body,
        )
        await self.repos.db.refresh(message, ["author_user", "author_contact"])
        await track_usage(
            self.repos, organization_id, HelpdeskUsageMetric.TICKETS_PER_MONTH
        )
        await notify_agents(
            self.helpdesk,
            ticket=ticket,
            notification_type=HelpdeskNotificationType.TICKET_CREATED,
            contact_name=contact.name,
        )

        schedule_task(
            send_email,
            address=contact.email,
            user_name=contact.name,
            email_template="ticket-received",
            locale=schema_in.locale or contact.locale,
            data={
                "organization_name": await self.sites.get_organization_name(site),
                "ticket_number": ticket.number,
                "ticket_subject": ticket.subject,
                "conversation_url": conversation_url(
                    site.slug, create_contact_token(contact)
                ),
            },
        )
        return WidgetTicketCreatedOut(
            ticket=await self._ticket_detail(ticket),
            access_token=create_contact_token(contact, ticket_id=ticket.id),
        )

    async def send_access_link(
        self,
        slug: str,
        schema_in: WidgetAccessLinkIn,
        schedule_task: Callable[..., Any],
    ) -> None:
        site = await self._site(slug)
        contact = await self.contacts.get_by_email(schema_in.email)
        # The response is the same whether or not the address is known, so the
        # endpoint cannot be used to discover who has contacted the organization.
        if contact is None:
            return
        schedule_task(
            send_email,
            address=contact.email,
            user_name=contact.name,
            email_template="ticket-access",
            locale=schema_in.locale or contact.locale,
            data={
                "organization_name": await self.sites.get_organization_name(site),
                "conversation_url": conversation_url(
                    site.slug, create_contact_token(contact)
                ),
            },
        )

    async def list_tickets(
        self, slug: str, access: ContactAccess
    ) -> WidgetTicketListOut:
        site = await self._site(slug)
        contact = await self._authorize(site, access)
        tickets = [
            ticket
            for ticket in await self.tickets.filter_by(contact_id=contact.id)
            if access.ticket_id is None or ticket.id == access.ticket_id
        ]
        tickets.sort(key=lambda ticket: ticket.last_message_at, reverse=True)
        return WidgetTicketListOut(
            contact_name=contact.name,
            tickets=[WidgetTicketOut.model_validate(ticket) for ticket in tickets],
        )

    async def get_ticket(
        self, slug: str, access: ContactAccess, ticket_id: int
    ) -> WidgetTicketDetailOut:
        site = await self._site(slug)
        await self._authorize(site, access)
        return await self._ticket_detail(await self._owned_ticket(access, ticket_id))

    async def reply(
        self,
        slug: str,
        access: ContactAccess,
        ticket_id: int,
        schema_in: WidgetMessageIn,
    ) -> WidgetMessageOut:
        site = await self._site(slug)
        contact = await self._authorize(site, access)
        ticket = await self._owned_ticket(access, ticket_id)
        if ticket.status == TicketStatus.CLOSED:
            raise ClientException(
                status.HTTP_409_CONFLICT,
                f"Ticket is closed. [{ticket_id=}]",
                error_code=HelpdeskErrorCode.TICKET_CLOSED,
            )

        message = await self.messages.create(
            ticket_id=ticket.id,
            author_type=MessageAuthorType.CONTACT,
            author_contact_id=contact.id,
            body=schema_in.body,
        )
        changes: dict[str, Any] = {"last_message_at": datetime.now(UTC)}
        if ticket.status != TicketStatus.OPEN:
            # The customer wrote back: the ticket is back in the team's queue.
            changes |= {"status": TicketStatus.OPEN, "resolved_at": None}
        ticket = await self.tickets.update(ticket, **changes)
        await notify_agents(
            self.helpdesk,
            ticket=ticket,
            notification_type=HelpdeskNotificationType.TICKET_CUSTOMER_REPLIED,
            contact_name=contact.name,
        )
        await self.repos.db.refresh(message, ["author_user", "author_contact"])
        return WidgetMessageOut.model_validate(message)

    async def _site(self, slug: str) -> SupportSite:
        site = await self.sites.get_by_slug(slug)
        if site is None or not site.widget_enabled:
            raise NotFoundException(f"Support site not found. [{slug=}]")
        organization_id = site.organization_id
        self.contacts.set_organization_scope(organization_id)
        self.tickets.set_organization_scope(organization_id)
        self.messages.set_organization_scope(organization_id)
        return site

    async def _authorize(self, site: SupportSite, access: ContactAccess) -> Contact:
        if access.organization_id != site.organization_id:
            raise NotAuthenticatedException("Contact token is for another site")
        contact = await self.contacts.get(access.contact_id)
        if contact is None:
            raise NotAuthenticatedException("Contact no longer exists")
        return contact

    async def _owned_ticket(self, access: ContactAccess, ticket_id: int) -> Ticket:
        ticket = await self.tickets.get(ticket_id)
        if (
            ticket is None
            or ticket.contact_id != access.contact_id
            or (access.ticket_id is not None and access.ticket_id != ticket_id)
        ):
            raise NotFoundException(f"Ticket not found. [{ticket_id=}]")
        return ticket

    async def _ticket_detail(self, ticket: Ticket) -> WidgetTicketDetailOut:
        messages = await self.messages.list_for_ticket(
            ticket.id, include_internal=False
        )
        return WidgetTicketDetailOut(
            **WidgetTicketOut.model_validate(ticket).model_dump(),
            messages=[WidgetMessageOut.model_validate(m) for m in messages],
        )
