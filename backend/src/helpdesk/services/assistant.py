import logging
from collections.abc import Sequence
from typing import Annotated

from anthropic import AsyncAnthropic
from fastapi import Depends, status

from src.helpdesk.assistant import (
    ANSWER_SYSTEM_PROMPT,
    REPLY_SYSTEM_PROMPT,
    GeneratedText,
    generate_cited_text,
    get_ai_client,
    require_client,
    untrusted,
)
from src.helpdesk.embeddings import Embedder, get_embedder
from src.helpdesk.enums import (
    AiFeature,
    AiRequestOutcome,
    HelpdeskErrorCode,
    HelpdeskUsageMetric,
    KnowledgeSourceType,
    MessageAuthorType,
    TicketStatus,
)
from src.helpdesk.models.ticket import Ticket
from src.helpdesk.models.ticket_message import TicketMessage
from src.helpdesk.repositories.ai_request_log import AiRequestLogRepository
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.retrieval import KnowledgeRetriever, Retrieval
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
        AiSourceOut(
            source_type=s.source_type,
            title=s.title,
            slug=s.slug,
            cited_text=s.cited_text,
        )
        for s in generated.sources
    ]


def _outcome(generated: GeneratedText) -> AiRequestOutcome:
    if generated.text and generated.sources:
        return AiRequestOutcome.GROUNDED
    return AiRequestOutcome.UNGROUNDED


def _cited_ids(
    generated: GeneratedText | None, source_type: KnowledgeSourceType
) -> list[int]:
    if generated is None:
        return []
    return [s.source_id for s in generated.sources if s.source_type == source_type]


async def _record(
    logs: AiRequestLogRepository,
    *,
    organization_id: int,
    feature: AiFeature,
    query: str,
    retrieval: Retrieval,
    outcome: AiRequestOutcome,
    generated: GeneratedText | None = None,
) -> None:
    await logs.record(
        organization_id=organization_id,
        feature=feature,
        query=query,
        retrieval_mode=retrieval.mode,
        chunk_ids=retrieval.chunk_ids,
        cited_article_ids=_cited_ids(generated, KnowledgeSourceType.ARTICLE),
        cited_document_ids=_cited_ids(generated, KnowledgeSourceType.DOCUMENT),
        outcome=outcome,
    )


def ticket_search_query(ticket: Ticket, messages: Sequence[TicketMessage]) -> str:
    """What to look up in the knowledge base for a ticket: the subject plus
    the customer's latest message (on a ticket an agent opened for the
    customer, the first public message). The whole thread would mostly add
    noise to the search."""
    public = [m for m in messages if not m.is_internal]
    latest = next(
        (m for m in reversed(public) if m.author_type == MessageAuthorType.CONTACT),
        public[0] if public else None,
    )
    return f"{ticket.subject}\n{latest.body}" if latest else ticket.subject


class ReplySuggestionService(BaseService):
    """Drafts an agent's reply to a ticket from its conversation, the help
    center and the team's internal knowledge."""

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
        client: Annotated[AsyncAnthropic | None, Depends(get_ai_client)],
        embedder: Annotated[Embedder | None, Depends(get_embedder)],
    ) -> None:
        super().__init__(repos)
        organization_id = current_user.organization_id
        self.tickets = repos.ticket
        self.tickets.set_organization_scope(organization_id)
        self.messages = repos.ticket_message
        self.messages.set_organization_scope(organization_id)
        self.retriever = KnowledgeRetriever(repos, embedder)
        self.logs = repos.ai_request_log
        self.current_user = current_user
        self.client = client

    async def suggest(self, ticket_id: int) -> ReplySuggestionOut:
        client = require_client(self.client)
        organization_id = self.current_user.organization_id
        ticket = await self.tickets.get_one(ticket_id)
        if ticket.status == TicketStatus.CLOSED:
            # A public reply would be refused (see TicketService.reply), so
            # don't spend an AI request drafting one.
            raise ClientException(
                status.HTTP_409_CONFLICT,
                f"Ticket is closed. [{ticket_id=}]",
                error_code=HelpdeskErrorCode.TICKET_CLOSED,
            )
        await require_within_limit(
            self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
        )

        messages = await self.messages.list_for_ticket(ticket.id)
        conversation = "\n\n".join(
            f"[{self._label(message)}]\n{message.body}" for message in messages
        )
        organization = await self.repos.organization.get(organization_id)
        prompt = (
            f"Company: {organization.name if organization else ''}\n"
            f"Ticket #{ticket.number}: {ticket.subject}\n"
            f"Customer: {ticket.contact.name}\n\n"
            f"{untrusted(conversation, 'conversation')}\n\n"
            "Draft the agent's reply to the customer's most recent message."
        )
        query = ticket_search_query(ticket, messages)
        # Agents may see internal knowledge; the draft is reviewed before
        # anything reaches the customer.
        retrieval = await self.retriever.retrieve(
            organization_id, query, include_internal=True
        )

        async def record(
            outcome: AiRequestOutcome, generated: GeneratedText | None = None
        ) -> None:
            await _record(
                self.logs,
                organization_id=organization_id,
                feature=AiFeature.REPLY_SUGGESTION,
                query=query,
                retrieval=retrieval,
                outcome=outcome,
                generated=generated,
            )

        try:
            # Without matching sources Claude still drafts from the conversation
            # and names what the agent should confirm.
            generated = await generate_cited_text(
                client, system=REPLY_SYSTEM_PROMPT, retrieval=retrieval, prompt=prompt
            )
            if not generated.text:
                raise ClientException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "The AI assistant returned an empty draft",
                    error_code=HelpdeskErrorCode.AI_DECLINED,
                )
        except ClientException:
            # Raising rolls back the request's transaction, so commit the log
            # row first to keep a trace of the failed attempt. Nothing else has
            # been written yet, and a failed attempt uses no quota.
            await record(AiRequestOutcome.FAILED)
            await self.repos.db.commit()
            raise

        await track_usage(
            self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
        )
        await record(_outcome(generated), generated)
        return ReplySuggestionOut(text=generated.text, sources=_sources(generated))

    @staticmethod
    def _label(message: TicketMessage) -> str:
        author = message.author_name or "unknown"
        if message.is_internal:
            return f"internal note by {author} - background only"
        if message.author_type == MessageAuthorType.CONTACT:
            return f"customer {author}"
        return f"agent {author}"


class WidgetAnswerService(BaseService):
    """Answers a customer's question from the published help center.

    Customers never see assistant errors or billing limits: whenever an
    answer can't be produced and grounded in an article, the result is simply
    "not answered" and the widget falls back to article search and a human.
    Internal knowledge is never used here.
    """

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        client: Annotated[AsyncAnthropic | None, Depends(get_ai_client)],
        embedder: Annotated[Embedder | None, Depends(get_embedder)],
    ) -> None:
        super().__init__(repos)
        self.sites = repos.support_site
        self.retriever = KnowledgeRetriever(repos, embedder)
        self.logs = repos.ai_request_log
        self.client = client

    async def answer(self, slug: str, schema_in: WidgetQuestionIn) -> WidgetAnswerOut:
        site = await self.sites.get_by_slug(slug)
        if site is None or not site.widget_enabled:
            raise NotFoundException(f"Support site not found. [{slug=}]")
        not_answered = WidgetAnswerOut(answered=False, text=None, sources=[])
        if self.client is None or not site.help_center_enabled:
            return not_answered

        organization_id = site.organization_id
        try:
            await require_within_limit(
                self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
            )
        except LimitExceededException:
            return not_answered

        question = schema_in.question
        retrieval = await self.retriever.retrieve(
            organization_id, question, include_internal=False
        )

        async def record(
            outcome: AiRequestOutcome, generated: GeneratedText | None = None
        ) -> None:
            await _record(
                self.logs,
                organization_id=organization_id,
                feature=AiFeature.WIDGET_ANSWER,
                query=question,
                retrieval=retrieval,
                outcome=outcome,
                generated=generated,
            )

        if not retrieval.passages:
            # Nothing to ground an answer in: don't spend a request on it.
            await record(AiRequestOutcome.NO_MATCH)
            return not_answered

        try:
            generated = await generate_cited_text(
                self.client,
                system=ANSWER_SYSTEM_PROMPT,
                retrieval=retrieval,
                prompt=untrusted(question, "question"),
            )
        except ClientException as exc:
            log.info("Widget answer unavailable. [%s, error=%s]", slug, exc.detail)
            await record(AiRequestOutcome.FAILED)
            return not_answered

        await track_usage(
            self.repos, organization_id, HelpdeskUsageMetric.AI_REQUESTS_PER_MONTH
        )
        outcome = _outcome(generated)
        await record(outcome, generated)
        if outcome != AiRequestOutcome.GROUNDED:
            return not_answered
        return WidgetAnswerOut(
            answered=True, text=generated.text, sources=_sources(generated)
        )
