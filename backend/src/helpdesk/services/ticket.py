from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, status

from src.helpdesk.contact_token import conversation_url, create_contact_token
from src.helpdesk.enums import (
    HelpdeskAuditAction,
    HelpdeskErrorCode,
    HelpdeskNotificationType,
    HelpdeskPermission,
    HelpdeskUsageMetric,
    MessageAuthorType,
    TicketChannel,
    TicketStatus,
)
from src.helpdesk.models.contact import Contact
from src.helpdesk.models.ticket import Ticket
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.repositories.ticket import TicketRepository
from src.helpdesk.schemas.ticket import (
    TicketAssigneeIn,
    TicketDetailOut,
    TicketIn,
    TicketMessageIn,
    TicketMessageOut,
    TicketOut,
    TicketPatch,
)
from src.platform.billing.dependencies import track_usage
from src.platform.core.dependencies import authenticate
from src.platform.core.exceptions import ClientException, ValidationException
from src.platform.core.security import Auth
from src.platform.services.base import ResourceService
from src.platform.services.mailer import send_email


def _status_timestamps(
    new_status: TicketStatus, ticket: Ticket
) -> dict[str, datetime | None]:
    now = datetime.now(UTC)
    if new_status == TicketStatus.RESOLVED:
        return {"resolved_at": now, "closed_at": None}
    if new_status == TicketStatus.CLOSED:
        return {"resolved_at": ticket.resolved_at or now, "closed_at": now}
    # Reopened: the ticket is back in the team's queue.
    return {"resolved_at": None, "closed_at": None}


class TicketService(ResourceService[TicketRepository, Ticket, TicketPatch, TicketOut]):
    current_user: Auth

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
    ) -> None:
        organization_id = current_user.organization_id
        self.repo = repos.ticket
        self.repo.set_organization_scope(organization_id)
        self.messages = repos.ticket_message
        self.messages.set_organization_scope(organization_id)
        self.contacts = repos.contact
        self.contacts.set_organization_scope(organization_id)
        self.sites = repos.support_site
        self.current_user = current_user
        super().__init__(repos)

    async def create_ticket(self, schema_in: TicketIn) -> TicketDetailOut:
        organization_id = self.current_user.organization_id
        if schema_in.assignee_id is not None:
            self.current_user.authorize(HelpdeskPermission.ASSIGN_TICKET)
            await self._assert_member(schema_in.assignee_id)
        contact = await self._resolve_contact(schema_in)

        ticket = await self.repo.create(
            number=await self.repo.next_number(),
            subject=schema_in.subject,
            priority=schema_in.priority,
            channel=TicketChannel.AGENT,
            contact_id=contact.id,
            assignee_id=schema_in.assignee_id,
            last_message_at=datetime.now(UTC),
        )
        await self.messages.create(
            ticket_id=ticket.id,
            author_type=MessageAuthorType.AGENT,
            author_user_id=self.current_user.id,
            body=schema_in.body,
        )
        await track_usage(
            self.repos, organization_id, HelpdeskUsageMetric.TICKETS_PER_MONTH
        )
        await self.log_audit(
            HelpdeskAuditAction.TICKET_CREATE,
            organization_id=organization_id,
            user_id=self.current_user.id,
            resource_type="ticket",
            resource_id=ticket.id,
            details={"number": ticket.number, "subject": ticket.subject},
        )
        await self._notify_assignee(ticket)
        return await self.get_ticket(ticket.id)

    async def get_ticket(self, identifier: int) -> TicketDetailOut:
        ticket = await self.get(identifier)
        messages = await self.messages.list_for_ticket(ticket.id)
        return TicketDetailOut(
            **TicketOut.model_validate(ticket).model_dump(),
            messages=[TicketMessageOut.model_validate(m) for m in messages],
        )

    async def patch_ticket(self, identifier: int, schema_in: TicketPatch) -> TicketOut:
        ticket = await self.get(identifier)
        # Every patchable column is required, so an explicit null is a no-op.
        changes: dict[str, Any] = {
            key: value
            for key, value in schema_in.model_dump(exclude_unset=True).items()
            if value is not None
        }
        new_status = changes.get("status")
        if new_status is not None and new_status != ticket.status:
            changes |= _status_timestamps(new_status, ticket)

        ticket = await self.repo.update(ticket, **changes)
        await self.log_audit(
            HelpdeskAuditAction.TICKET_UPDATE,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="ticket",
            resource_id=ticket.id,
            details=schema_in.model_dump(mode="json", exclude_unset=True),
        )
        return TicketOut.model_validate(ticket)

    async def assign_ticket(
        self, identifier: int, schema_in: TicketAssigneeIn
    ) -> TicketOut:
        ticket = await self.get(identifier)
        if schema_in.assignee_id is not None:
            await self._assert_member(schema_in.assignee_id)
        previous_assignee_id = ticket.assignee_id

        ticket = await self.repo.update(ticket, assignee_id=schema_in.assignee_id)
        await self.repos.db.refresh(ticket, ["assignee"])
        await self.log_audit(
            HelpdeskAuditAction.TICKET_ASSIGN,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="ticket",
            resource_id=ticket.id,
            details={"from": previous_assignee_id, "to": schema_in.assignee_id},
        )
        if schema_in.assignee_id != previous_assignee_id:
            await self._notify_assignee(ticket)
        return TicketOut.model_validate(ticket)

    async def reply(
        self,
        identifier: int,
        schema_in: TicketMessageIn,
        schedule_task: Callable[..., Any],
    ) -> TicketMessageOut:
        ticket = await self.get(identifier)
        if not schema_in.is_internal and ticket.status == TicketStatus.CLOSED:
            raise ClientException(
                status.HTTP_409_CONFLICT,
                f"Ticket is closed. [ticket_id={identifier}]",
                error_code=HelpdeskErrorCode.TICKET_CLOSED,
            )

        message = await self.messages.create(
            ticket_id=ticket.id,
            author_type=MessageAuthorType.AGENT,
            author_user_id=self.current_user.id,
            body=schema_in.body,
            is_internal=schema_in.is_internal,
        )
        if not schema_in.is_internal:
            await self._record_public_reply(ticket)
            await self._email_reply(ticket, schema_in.body, schedule_task)

        await self.repos.db.refresh(message, ["author_user", "author_contact"])
        return TicketMessageOut.model_validate(message)

    async def delete_ticket(self, identifier: int) -> None:
        await super().delete(identifier)
        await self.log_audit(
            HelpdeskAuditAction.TICKET_DELETE,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="ticket",
            resource_id=identifier,
        )

    async def _resolve_contact(self, schema_in: TicketIn) -> Contact:
        if schema_in.contact_id is not None:
            return await self.contacts.get_one(schema_in.contact_id)
        assert schema_in.contact is not None
        existing = await self.contacts.get_by_email(schema_in.contact.email)
        if existing is not None:
            return existing
        contact = await self.contacts.create(**schema_in.contact.model_dump())
        await self.log_audit(
            HelpdeskAuditAction.CONTACT_CREATE,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="contact",
            resource_id=contact.id,
            details={"email": contact.email},
        )
        return contact

    async def _assert_member(self, user_id: int) -> None:
        membership = await self.repos.user_organization.get_by_user_and_organization(
            user_id, self.current_user.organization_id
        )
        if membership is None:
            raise ValidationException(
                f"Assignee is not a member of the organization. [{user_id=}]",
                error_code=HelpdeskErrorCode.ASSIGNEE_NOT_MEMBER,
            )

    async def _record_public_reply(self, ticket: Ticket) -> None:
        now = datetime.now(UTC)
        changes: dict[str, Any] = {"last_message_at": now}
        if ticket.first_response_at is None:
            changes["first_response_at"] = now
        if ticket.status == TicketStatus.OPEN:
            # The team has answered; the ticket now waits on the customer.
            changes["status"] = TicketStatus.PENDING
        await self.repo.update(ticket, **changes)

    async def _email_reply(
        self, ticket: Ticket, body: str, schedule_task: Callable[..., Any]
    ) -> None:
        organization_id = self.current_user.organization_id
        organization = await self.repos.organization.get(organization_id)
        organization_name = organization.name if organization else ""
        site = await self.sites.get_or_create_for_organization(
            organization_id, organization_name
        )
        contact = ticket.contact
        schedule_task(
            send_email,
            address=contact.email,
            user_name=contact.name,
            email_template="ticket-reply",
            locale=contact.locale,
            data={
                "organization_name": organization_name,
                "agent_name": self.current_user.name,
                "ticket_number": ticket.number,
                "ticket_subject": ticket.subject,
                "message_body": body,
                "conversation_url": conversation_url(
                    site.slug, create_contact_token(contact)
                ),
            },
        )

    async def _notify_assignee(self, ticket: Ticket) -> None:
        if ticket.assignee_id is None or ticket.assignee_id == self.current_user.id:
            return
        await self.repos.notification.create(
            user_id=ticket.assignee_id,
            organization_id=self.current_user.organization_id,
            type=HelpdeskNotificationType.TICKET_ASSIGNED,
            payload={
                "ticket_id": ticket.id,
                "number": ticket.number,
                "subject": ticket.subject,
                "assigned_by": self.current_user.name,
            },
        )
