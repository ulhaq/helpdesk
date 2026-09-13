from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.helpdesk.enums import TicketPriority, TicketStatus
from src.helpdesk.models.contact import Contact
from src.platform.models.mixins import ResourceModel
from src.platform.models.user import User


class Ticket(ResourceModel):
    __tablename__ = "ticket"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "number", name="uq_ticket_organization_number"
        ),
    )

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Human-facing reference, sequential per organization (#1, #2, ...).
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TicketStatus.OPEN, index=True
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TicketPriority.NORMAL
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    contact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("contact.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignee_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    contact: Mapped[Contact] = relationship(lazy="selectin")
    assignee: Mapped[User | None] = relationship(lazy="selectin")
