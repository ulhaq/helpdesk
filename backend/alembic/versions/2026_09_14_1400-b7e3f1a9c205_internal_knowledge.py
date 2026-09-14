"""helpdesk: internal knowledge documents and chunk embeddings (pgvector)

Revision ID: b7e3f1a9c205
Revises: 9d2a5c7e4f13
Create Date: 2026-09-14 14:00:00.000000

Needs PostgreSQL with pgvector available (the pgvector/pgvector image).
CREATE EXTENSION requires a superuser unless the extension already exists:
fresh Docker volumes get it from scripts/db-init.sh; existing databases need
`CREATE EXTENSION IF NOT EXISTS vector` run once as the postgres user.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "b7e3f1a9c205"
down_revision: str | None = "9d2a5c7e4f13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# EMBEDDING_DIMENSIONS at this revision.
_DIMENSIONS = 1024

_RENAMED_INDEXES = [
    ("ix_kb_article_chunk_organization_id", "ix_knowledge_chunk_organization_id"),
    ("ix_kb_article_chunk_article_id", "ix_knowledge_chunk_article_id"),
    ("ix_kb_article_chunk_search", "ix_knowledge_chunk_search"),
]


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_document",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=127), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["author_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_document_organization_id",
        "knowledge_document",
        ["organization_id"],
    )

    # Article chunks become knowledge chunks of either source.
    op.rename_table("kb_article_chunk", "knowledge_chunk")
    op.execute("ALTER SEQUENCE kb_article_chunk_id_seq RENAME TO knowledge_chunk_id_seq")
    for old, new in _RENAMED_INDEXES:
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")
    op.alter_column(
        "knowledge_chunk", "article_id", existing_type=sa.Integer(), nullable=True
    )
    op.add_column(
        "knowledge_chunk", sa.Column("document_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "knowledge_chunk_document_id_fkey",
        "knowledge_chunk",
        "knowledge_document",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_knowledge_chunk_document_id", "knowledge_chunk", ["document_id"]
    )
    op.create_check_constraint(
        "ck_knowledge_chunk_one_source",
        "knowledge_chunk",
        "(article_id IS NULL) <> (document_id IS NULL)",
    )
    op.add_column(
        "knowledge_chunk",
        sa.Column("embedding", Vector(_DIMENSIONS), nullable=True),
    )
    op.add_column(
        "knowledge_chunk",
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunk_embedding ON knowledge_chunk "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.add_column(
        "ai_request_log",
        sa.Column(
            "cited_document_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_request_log", "cited_document_ids")

    op.execute("DROP INDEX ix_knowledge_chunk_embedding")
    op.drop_column("knowledge_chunk", "embedding_model")
    op.drop_column("knowledge_chunk", "embedding")
    op.execute("DELETE FROM knowledge_chunk WHERE document_id IS NOT NULL")
    op.drop_constraint(
        "ck_knowledge_chunk_one_source", "knowledge_chunk", type_="check"
    )
    op.drop_index("ix_knowledge_chunk_document_id", table_name="knowledge_chunk")
    op.drop_constraint(
        "knowledge_chunk_document_id_fkey", "knowledge_chunk", type_="foreignkey"
    )
    op.drop_column("knowledge_chunk", "document_id")
    op.alter_column(
        "knowledge_chunk", "article_id", existing_type=sa.Integer(), nullable=False
    )
    for old, new in reversed(_RENAMED_INDEXES):
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    op.execute("ALTER SEQUENCE knowledge_chunk_id_seq RENAME TO kb_article_chunk_id_seq")
    op.rename_table("knowledge_chunk", "kb_article_chunk")

    op.drop_index(
        "ix_knowledge_document_organization_id", table_name="knowledge_document"
    )
    op.drop_table("knowledge_document")
    # The vector extension stays installed; other schemas may use it.
