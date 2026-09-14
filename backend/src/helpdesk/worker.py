"""Helpdesk background loops, registered in `worker.py`.

- Auto-close: closes tickets that stayed resolved without the customer writing
  back, so the resolved state means "waiting for confirmation" rather than
  piling up forever.
- AI request log retention: deletes assistant request logs (which contain
  customer text) once they're older than the retention period.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.config import settings
from src.helpdesk.repositories.ai_request_log import AiRequestLogRepository
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


async def _run_once(session_factory: Any) -> None:
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
            await _run_once(session_factory)
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
