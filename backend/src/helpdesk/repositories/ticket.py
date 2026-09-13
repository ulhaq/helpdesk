from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import Row, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.enums import TicketStatus
from src.helpdesk.models.ticket import Ticket
from src.platform.core.exceptions import UnscopedQueryError
from src.platform.models.organization import Organization
from src.platform.repositories.base import OrganizationScopedRepository


class TicketRepository(OrganizationScopedRepository[Ticket]):
    search_fields: ClassVar[list[str]] = ["subject"]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Ticket, db)

    async def next_number(self) -> int:
        """The next per-organization ticket number.

        Locks the organization row first so concurrent creates in the same
        organization serialize instead of colliding on the unique
        (organization_id, number) constraint. Deleted tickets keep their
        numbers, so they are counted too.
        """
        organization_id = self._organization_id
        if organization_id is None:
            raise UnscopedQueryError(
                "Ticket numbers are allocated per organization. "
                "Call set_organization_scope(organization_id) first."
            )
        await self.db.execute(
            select(Organization.id)
            .where(Organization.id == organization_id)
            .with_for_update()
        )
        rs = await self.db.execute(
            select(func.coalesce(func.max(Ticket.number), 0)).where(
                Ticket.organization_id == organization_id
            )
        )
        return int(rs.scalar_one()) + 1

    async def unassign_user(self, user_id: int) -> None:
        for ticket in await self.filter_by(assignee_id=user_id):
            ticket.assignee_id = None
        await self.save()

    async def report_rows(self, since: datetime) -> Sequence[Row[Any]]:
        """The columns reports need, for tickets created or resolved since
        `since` plus the whole current backlog."""
        stmt = select(
            Ticket.created_at,
            Ticket.first_response_at,
            Ticket.resolved_at,
            Ticket.status,
            Ticket.channel,
            Ticket.priority,
            Ticket.assignee_id,
        ).where(
            or_(
                Ticket.created_at >= since,
                Ticket.resolved_at >= since,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]),
            )
        )
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        rs = await self.db.execute(stmt)
        return rs.all()

    async def close_resolved_before(self, cutoff: datetime) -> int:
        """Close tickets resolved before `cutoff`; returns how many. Workers
        call this on `.unscoped` to sweep every organization."""
        now = datetime.now(UTC)
        stmt = update(Ticket).where(
            Ticket.status == TicketStatus.RESOLVED,
            Ticket.resolved_at < cutoff,
            Ticket.deleted_at.is_(None),
        )
        if self._organization_id is not None:
            stmt = stmt.where(Ticket.organization_id == self._organization_id)
        elif not self._allow_unscoped:
            raise UnscopedQueryError(
                "close_resolved_before needs an organization scope or `.unscoped`."
            )
        stmt = stmt.values(
            status=TicketStatus.CLOSED, closed_at=now, updated_at=now
        ).returning(Ticket.id)
        rs = await self.db.execute(stmt)
        return len(rs.all())
