from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.helpdesk.enums import MessageAuthorType
from src.helpdesk.models.contact import Contact
from src.platform.models.mixins import ResourceModel
from src.platform.models.user import User


class TicketMessage(ResourceModel):
    __tablename__ = "ticket_message"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_type: Mapped[str] = mapped_column(String(16), nullable=False)
    author_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    author_contact_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Internal notes are visible to the team only, never to the contact.
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    author_user: Mapped[User | None] = relationship(lazy="selectin")
    author_contact: Mapped[Contact | None] = relationship(lazy="selectin")

    @property
    def author_name(self) -> str | None:
        author = (
            self.author_user
            if self.author_type == MessageAuthorType.AGENT
            else self.author_contact
        )
        return author.name if author is not None else None
