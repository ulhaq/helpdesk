from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.models.mixins import ResourceModel


class Contact(ResourceModel):
    """A customer of the organization. Contacts have no platform account: they
    reach the team through the widget and are identified by email, which is
    stored lowercased and unique among an organization's active contacts."""

    __tablename__ = "contact"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
