from datetime import date, datetime

from pydantic import BaseModel


class CountByKey(BaseModel):
    key: str
    count: int


class DurationStats(BaseModel):
    median_seconds: int | None
    average_seconds: int | None
    # How many tickets the figures are based on.
    sample_size: int


class DailyVolume(BaseModel):
    day: date
    created: int
    resolved: int


class AgentWorkload(BaseModel):
    user_id: int
    name: str
    # Open or pending tickets assigned to the agent right now.
    open: int
    # Tickets currently assigned to the agent that were resolved in the period.
    resolved: int


class ReportSummaryOut(BaseModel):
    period_days: int
    since: datetime
    created: int
    resolved: int
    # Open or pending right now, regardless of when they were created.
    backlog: int
    unassigned_backlog: int
    # Over tickets created in the period that have been answered.
    first_response: DurationStats
    # Over tickets resolved in the period, from creation to resolution.
    resolution: DurationStats
    # Current state of tickets created in the period; every key is listed.
    by_status: list[CountByKey]
    by_channel: list[CountByKey]
    by_priority: list[CountByKey]
    daily: list[DailyVolume]
    agents: list[AgentWorkload]
