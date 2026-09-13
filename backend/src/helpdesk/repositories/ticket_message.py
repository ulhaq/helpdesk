from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.models.ticket_message import TicketMessage
from src.platform.repositories.base import OrganizationScopedRepository


class TicketMessageRepository(OrganizationScopedRepository[TicketMessage]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(TicketMessage, db)

    async def list_for_ticket(
        self, ticket_id: int, *, include_internal: bool = True
    ) -> Sequence[TicketMessage]:
        """A ticket's conversation, oldest first."""
        stmt = select(TicketMessage).filter(TicketMessage.ticket_id == ticket_id)
        if not include_internal:
            stmt = stmt.filter(TicketMessage.is_internal.is_(False))
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        stmt = stmt.order_by(TicketMessage.created_at, TicketMessage.id)
        rs = await self.db.execute(stmt)
        return rs.unique().scalars().all()
