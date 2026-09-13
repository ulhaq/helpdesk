from collections import Counter
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from statistics import mean, median
from typing import Annotated

from fastapi import Depends

from src.helpdesk.enums import TicketChannel, TicketPriority, TicketStatus
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.schemas.reports import (
    AgentWorkload,
    CountByKey,
    DailyVolume,
    DurationStats,
    ReportSummaryOut,
)
from src.platform.core.dependencies import authenticate
from src.platform.core.security import Auth
from src.platform.services.base import BaseService

_BACKLOG = {TicketStatus.OPEN, TicketStatus.PENDING}


def _as_utc(value: datetime) -> datetime:
    # SQLite hands back naive datetimes; every stored time is UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _durations(seconds: list[float]) -> DurationStats:
    if not seconds:
        return DurationStats(median_seconds=None, average_seconds=None, sample_size=0)
    return DurationStats(
        median_seconds=round(median(seconds)),
        average_seconds=round(mean(seconds)),
        sample_size=len(seconds),
    )


def _counts(counter: Counter[str], keys: type[StrEnum]) -> list[CountByKey]:
    return [CountByKey(key=key, count=counter[key]) for key in keys]


class ReportService(BaseService):
    """Support metrics for the current organization.

    Computed in Python over one bounded query (at most a year of tickets plus
    the open backlog), which keeps the arithmetic identical across databases.
    """

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
    ) -> None:
        super().__init__(repos)
        self.tickets = repos.ticket
        self.tickets.set_organization_scope(current_user.organization_id)
        self.agents = repos.agent

    async def summary(self, days: int) -> ReportSummaryOut:
        today = datetime.now(UTC).date()
        first_day = today - timedelta(days=days - 1)
        since = datetime.combine(first_day, time.min, tzinfo=UTC)

        created_per_day: Counter = Counter()
        resolved_per_day: Counter = Counter()
        by_status: Counter[str] = Counter()
        by_channel: Counter[str] = Counter()
        by_priority: Counter[str] = Counter()
        open_per_agent: Counter[int] = Counter()
        resolved_per_agent: Counter[int] = Counter()
        first_response: list[float] = []
        resolution: list[float] = []
        backlog = unassigned_backlog = 0

        for row in await self.tickets.report_rows(since):
            created_at = _as_utc(row.created_at)
            if row.status in _BACKLOG:
                backlog += 1
                if row.assignee_id is None:
                    unassigned_backlog += 1
                else:
                    open_per_agent[row.assignee_id] += 1

            if created_at >= since:
                created_per_day[created_at.date()] += 1
                by_status[row.status] += 1
                by_channel[row.channel] += 1
                by_priority[row.priority] += 1
                if row.first_response_at is not None:
                    answered_at = _as_utc(row.first_response_at)
                    first_response.append((answered_at - created_at).total_seconds())

            if row.resolved_at is not None:
                resolved_at = _as_utc(row.resolved_at)
                if resolved_at >= since:
                    resolved_per_day[resolved_at.date()] += 1
                    resolution.append((resolved_at - created_at).total_seconds())
                    if row.assignee_id is not None:
                        resolved_per_agent[row.assignee_id] += 1

        names = await self.agents.names(set(open_per_agent) | set(resolved_per_agent))
        agents = sorted(
            (
                AgentWorkload(
                    user_id=user_id,
                    name=name,
                    open=open_per_agent[user_id],
                    resolved=resolved_per_agent[user_id],
                )
                for user_id, name in names.items()
            ),
            key=lambda agent: (-agent.open, -agent.resolved, agent.name),
        )

        return ReportSummaryOut(
            period_days=days,
            since=since,
            created=sum(created_per_day.values()),
            resolved=sum(resolved_per_day.values()),
            backlog=backlog,
            unassigned_backlog=unassigned_backlog,
            first_response=_durations(first_response),
            resolution=_durations(resolution),
            by_status=_counts(by_status, TicketStatus),
            by_channel=_counts(by_channel, TicketChannel),
            by_priority=_counts(by_priority, TicketPriority),
            daily=[
                DailyVolume(
                    day=day,
                    created=created_per_day[day],
                    resolved=resolved_per_day[day],
                )
                for day in (first_day + timedelta(days=n) for n in range(days))
            ],
            agents=agents,
        )
