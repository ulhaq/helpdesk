from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.helpdesk.embeddings import EMBEDDING_DIMENSIONS
from src.platform.models.mixins import ResourceModel


class KnowledgeDocument(ResourceModel):
    """Internal knowledge the team uploads or pastes for the AI assistant.

    Team-only: used for agent reply drafts, never for widget answers or the
    public help center.
    """

    __tablename__ = "knowledge_document"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # KnowledgeDocumentSource: pasted text or an uploaded file.
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # TextFormat: decides how the text is split (headings or windows).
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    # Extracted text; uploaded files themselves aren't kept.
    text: Mapped[str] = mapped_column(Text, nullable=False)


class KnowledgeChunk(ResourceModel):
    """A section of a help center article or an internal document - the unit
    the AI assistant retrieves.

    Rebuilt whenever its source's text changes (`src.helpdesk.kb_chunks`).
    On PostgreSQL, `ix_knowledge_chunk_search` (GIN) serves full-text search
    and `ix_knowledge_chunk_embedding` (HNSW) serves semantic search.
    """

    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        CheckConstraint(
            "(article_id IS NULL) <> (document_id IS NULL)",
            name="ck_knowledge_chunk_one_source",
        ),
    )

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("kb_article.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_document.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # "Title > Section > Subsection"
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Filled in by the embedding worker; deferred so searches don't load
    # thousands of floats they don't use. JSON on SQLite (tests).
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS).with_variant(JSON(), "sqlite"),
        nullable=True,
        deferred=True,
    )
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
