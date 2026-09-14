"""Helpdesk background loops, registered in `worker.py`.

- Auto-close: closes tickets that stayed resolved without the customer writing
  back, so the resolved state means "waiting for confirmation" rather than
  piling up forever.
- AI request log retention: deletes assistant request logs (which contain
  customer text) once they're older than the retention period.
- Embeddings: embeds new and changed knowledge chunks for semantic search,
  and re-embeds everything after an embedding model change.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.config import settings
from src.helpdesk.embeddings import Embedder, get_embedder
from src.helpdesk.repositories.ai_request_log import AiRequestLogRepository
from src.helpdesk.repositories.knowledge import KnowledgeChunkRepository
from src.helpdesk.repositories.ticket import TicketRepository
from src.platform.repositories.worker_run import WorkerRunRepository

log = logging.getLogger(__name__)

WORKER_TYPE = "helpdesk_auto_close"
_AI_LOG_RETENTION_INTERVAL_SECONDS = 24 * 60 * 60


async def close_stale_resolved_tickets(
    session: AsyncSession, older_than_days: int
) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    # Intentionally cross-tenant: one sweep covers every organization.
    return await TicketRepository(session).unscoped.close_resolved_before(cutoff)


async def purge_ai_request_logs(session: AsyncSession, older_than_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    # Intentionally cross-tenant: one sweep covers every organization.
    return await AiRequestLogRepository(session).unscoped.delete_before(cutoff)


async def embed_pending_chunks(
    session_factory: Any, embedder: Embedder, batch_size: int
) -> int:
    """Embed one batch of chunks; returns how many. The embedding call runs
    between two short transactions, never inside one."""
    async with session_factory() as session:
        # Intentionally cross-tenant: one worker embeds every organization.
        chunks = KnowledgeChunkRepository(session).unscoped
        pending = await chunks.pending_embeddings(embedder.model, limit=batch_size)
        texts = {chunk.id: f"{chunk.heading}\n\n{chunk.content}" for chunk in pending}
    if not texts:
        return 0

    vectors = await embedder.embed(list(texts.values()), "document")

    async with session_factory() as session:
        async with session.begin():
            await KnowledgeChunkRepository(session).unscoped.store_embeddings(
                dict(zip(texts, vectors, strict=True)), model=embedder.model
            )
    return len(texts)


async def _run_auto_close_once(session_factory: Any) -> None:
    # Transaction 1: commit the run record so 'running' is immediately visible
    async with session_factory() as session:
        async with session.begin():
            run_id = (await WorkerRunRepository(session).create(WORKER_TYPE)).id

    # Transaction 2: do the work and write the final run status
    async with session_factory() as session:
        async with session.begin():
            closed = await close_stale_resolved_tickets(
                session, settings.auto_close_resolved_after_days
            )
            await WorkerRunRepository(session).finish(
                run_id=run_id,
                status="success",
                items_processed=closed,
                changes_detected=closed,
                error_count=0,
            )
    log.info("Helpdesk auto-close: closed %d ticket(s)", closed)


async def run_auto_close_loop(session_factory: Any) -> None:
    if settings.auto_close_resolved_after_days <= 0:
        log.info("Helpdesk auto-close is disabled")
        return
    while True:
        try:
            await _run_auto_close_once(session_factory)
        except Exception as exc:
            log.error("Helpdesk auto-close loop error: %s", exc, exc_info=True)
        await asyncio.sleep(settings.auto_close_interval_seconds)


async def run_ai_request_log_retention_loop(session_factory: Any) -> None:
    if settings.ai_request_log_retention_days <= 0:
        log.info("AI request log retention is disabled")
        return
    while True:
        try:
            async with session_factory() as session:
                async with session.begin():
                    deleted = await purge_ai_request_logs(
                        session, settings.ai_request_log_retention_days
                    )
            log.info("AI request log retention: deleted %d log(s)", deleted)
        except Exception as exc:
            log.error("AI request log retention error: %s", exc, exc_info=True)
        await asyncio.sleep(_AI_LOG_RETENTION_INTERVAL_SECONDS)


async def run_embedding_loop(session_factory: Any) -> None:
    embedder = get_embedder()
    if embedder is None:
        log.info("No embedding provider configured; semantic search is off")
        return
    batch_size = settings.embedding_batch_size
    while True:
        embedded = 0
        try:
            embedded = await embed_pending_chunks(session_factory, embedder, batch_size)
            if embedded:
                log.info(
                    "Embedded %d knowledge chunk(s) with %s", embedded, embedder.model
                )
        except Exception as exc:
            log.error("Embedding loop error: %s", exc, exc_info=True)
        # A full batch means there's likely more waiting.
        if embedded < batch_size:
            await asyncio.sleep(settings.embedding_interval_seconds)
