"""Helpdesk background loop, registered in `worker.py`.

Closes tickets that stayed resolved without the customer writing back, so the
resolved state means "waiting for confirmation" rather than piling up forever.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.config import settings
from src.helpdesk.repositories.ticket import TicketRepository
from src.platform.repositories.worker_run import WorkerRunRepository

log = logging.getLogger(__name__)

WORKER_TYPE = "helpdesk_auto_close"


async def close_stale_resolved_tickets(
    session: AsyncSession, older_than_days: int
) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    # Intentionally cross-tenant: one sweep covers every organization.
    return await TicketRepository(session).unscoped.close_resolved_before(cutoff)


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
