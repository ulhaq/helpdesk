import logging
from typing import Annotated

from anthropic import AsyncAnthropic
from fastapi import Depends

from src.helpdesk.assistant import (
    ANSWER_SYSTEM_PROMPT,
    REPLY_SYSTEM_PROMPT,
    GeneratedText,
    generate_cited_text,
    get_ai_client,
    require_client,
    untrusted,
)
from src.helpdesk.config import settings
from src.helpdesk.enums import HelpdeskUsageMetric, MessageAuthorType
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.schemas.assistant import (
    AiSourceOut,
    ReplySuggestionOut,
    WidgetAnswerOut,
    WidgetQuestionIn,
)
from src.platform.billing.dependencies import require_within_limit, track_usage
from src.platform.core.dependencies import authenticate
from src.platform.core.exceptions import (
    ClientException,
    LimitExceededException,
    NotFoundException,
)
from src.platform.core.security import Auth
from src.platform.services.base import BaseService

log = logging.getLogger(__name__)


def _sources(generated: GeneratedText) -> list[AiSourceOut]:
    return [
        AiSourceOut(title=s.title, slug=s.slug, cited_text=s.cited_text)
        for s in generated.sources
    ]


class ReplySuggestionService(BaseService):
    """Drafts an agent's reply to a ticket from its conversation and the
    organization's help center."""

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
        client: Annotated[AsyncAnthropic | None, Depends(get_ai_client)],
    ) -> None:
        super().__init__(repos)
        organization_id = current_user.organization_id
        self.tickets = repos.ticket
        self.tickets.set_organization_scope(organization_id)
        self.messages = repos.ticket_message
        self.messages.set_organization_scope(organization_id)
        self.articles = repos.kb_article
        self.articles.set_organization_scope(organization_id)
        self.current_user = current_user
        self.client = client

    async def suggest(self, ticket_id: int) -> ReplySuggestionOut:
        client = require_client(self.client)
        organization_id = self.current_user.organization_id
        ticket = await self.tickets.get_one(ticket_id)
        await require_within_limit(
            self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
        )

        conversation = "\n\n".join(
            f"[{self._label(message)}]\n{message.body}"
            for message in await self.messages.list_for_ticket(ticket.id)
        )
        organization = await self.repos.organization.get(organization_id)
        prompt = (
            f"Company: {organization.name if organization else ''}\n"
            f"Ticket #{ticket.number}: {ticket.subject}\n"
            f"Customer: {ticket.contact.name}\n\n"
            f"{untrusted(conversation, 'conversation')}\n\n"
            "Draft the agent's reply to the customer's most recent message."
        )
        generated = await generate_cited_text(
            client,
            system=REPLY_SYSTEM_PROMPT,
            articles=await self.articles.list_published(
                order="title", limit=settings.ai_max_articles
            ),
            prompt=prompt,
        )
        await track_usage(
            self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
        )
        return ReplySuggestionOut(text=generated.text, sources=_sources(generated))

    @staticmethod
    def _label(message: object) -> str:
        author = getattr(message, "author_name", None) or "unknown"
        if getattr(message, "is_internal", False):
            return f"internal note by {author} - background only"
        if getattr(message, "author_type", None) == MessageAuthorType.CONTACT:
            return f"customer {author}"
        return f"agent {author}"


class WidgetAnswerService(BaseService):
    """Answers a customer's question from the published help center.

    Customers never see assistant errors or billing limits: whenever an
    answer can't be produced and grounded in an article, the result is simply
    "not answered" and the widget falls back to article search and a human.
    """

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        client: Annotated[AsyncAnthropic | None, Depends(get_ai_client)],
    ) -> None:
        super().__init__(repos)
        self.sites = repos.support_site
        self.articles = repos.kb_article
        self.client = client

    async def answer(self, slug: str, schema_in: WidgetQuestionIn) -> WidgetAnswerOut:
        site = await self.sites.get_by_slug(slug)
        if site is None or not site.widget_enabled:
            raise NotFoundException(f"Support site not found. [{slug=}]")
        not_answered = WidgetAnswerOut(answered=False, text=None, sources=[])
        if self.client is None or not site.help_center_enabled:
            return not_answered

        organization_id = site.organization_id
        self.articles.set_organization_scope(organization_id)
        articles = await self.articles.list_published(
            order="title", limit=settings.ai_max_articles
        )
        if not articles:
            return not_answered

        try:
            await require_within_limit(
                self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
            )
            generated = await generate_cited_text(
                self.client,
                system=ANSWER_SYSTEM_PROMPT,
                articles=articles,
                prompt=untrusted(schema_in.question, "question"),
            )
        except LimitExceededException:
            return not_answered
        except ClientException as exc:
            log.info("Widget answer unavailable. [%s, error=%s]", slug, exc.detail)
            return not_answered

        await track_usage(
            self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
        )
        if not generated.text or not generated.sources:
            return not_answered
        return WidgetAnswerOut(
            answered=True, text=generated.text, sources=_sources(generated)
        )
