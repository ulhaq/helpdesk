from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.helpdesk.enums import ArticleStatus
from src.platform.models.mixins import ResourceModel


class KbCategory(ResourceModel):
    __tablename__ = "kb_category"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Help center URL segment; unique among the organization's active
    # categories (enforced by the service, so deleted slugs can be reused).
    slug: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class KbArticle(ResourceModel):
    __tablename__ = "kb_article"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("kb_category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    author_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Unique among the organization's active articles, like KbCategory.slug.
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Markdown source, rendered by `src.helpdesk.markdown`.
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ArticleStatus.DRAFT, index=True
    )
    # First publication; kept when an article is unpublished and republished.
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    category: Mapped[KbCategory | None] = relationship(lazy="selectin")


class KbArticleChunk(ResourceModel):
    """A section of an article - the unit the AI assistant retrieves.

    Rebuilt whenever the article's title or body changes (split by
    `src.helpdesk.kb_chunks`). On PostgreSQL a GIN expression index
    (`ix_kb_article_chunk_search`, see the kb_retrieval migration) serves
    full-text search over the heading and content.
    """

    __tablename__ = "kb_article_chunk"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("kb_article.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # "Article title > Section > Subsection"
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
