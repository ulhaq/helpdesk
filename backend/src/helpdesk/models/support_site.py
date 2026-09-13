from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.models.mixins import ResourceModelBase

DEFAULT_BRAND_COLOR = "#293e70"


class SupportSite(ResourceModelBase):
    """An organization's public support presence: the slug its widget is
    and help center are
    reached at, plus their branding. One per organization, created on first use.
    """

    __tablename__ = "support_site"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    brand_color: Mapped[str] = mapped_column(
        String(7), nullable=False, default=DEFAULT_BRAND_COLOR
    )
    greeting: Mapped[str | None] = mapped_column(String(255), nullable=True)
    widget_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    help_center_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
