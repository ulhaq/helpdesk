from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.models.mixins import ResourceModel


class AiRequestLog(ResourceModel):
    """One AI assistant request: what was searched for, which knowledge base
    sections were retrieved and how it turned out. Used to spot retrieval
    misses (e.g. `no_match` or `ungrounded` while a matching article exists).

    Queries contain customer text, so rows are purged after
    `HELPDESK_AI_REQUEST_LOG_RETENTION_DAYS` by the helpdesk worker.
    """

    __tablename__ = "ai_request_log"
    # The retention sweep deletes by age.
    __table_args__ = (Index("ix_ai_request_log_created_at", "created_at"),)

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    chunk_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    cited_article_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list
    )
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
