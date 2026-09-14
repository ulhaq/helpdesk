"""helpdesk: knowledge base chunks for AI retrieval, AI request log

Revision ID: 9d2a5c7e4f13
Revises: 3f6b8e1c2a47
Create Date: 2026-09-14 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op
from src.helpdesk.kb_chunks import split_article

revision: str = "9d2a5c7e4f13"
down_revision: str | None = "3f6b8e1c2a47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must stay identical to `_SEARCH_VECTOR` in src/helpdesk/repositories/kb.py.
_SEARCH_VECTOR = (
    "setweight(to_tsvector('simple'::regconfig, heading), 'A'::\"char\") || "
    "setweight(to_tsvector('simple'::regconfig, content), 'B'::\"char\")"
)

_article_table = sa.table(
    "kb_article",
    sa.column("id", sa.Integer),
    sa.column("organization_id", sa.Integer),
    sa.column("title", sa.String),
    sa.column("body", sa.Text),
    sa.column("deleted_at", sa.DateTime),
)

_chunk_table = sa.table(
    "kb_article_chunk",
    sa.column("organization_id", sa.Integer),
    sa.column("article_id", sa.Integer),
    sa.column("position", sa.Integer),
    sa.column("heading", sa.Text),
    sa.column("content", sa.Text),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
    sa.column("deleted_at", sa.DateTime),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "kb_article_chunk",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["article_id"], ["kb_article.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kb_article_chunk_organization_id", "kb_article_chunk", ["organization_id"]
    )
    op.create_index("ix_kb_article_chunk_article_id", "kb_article_chunk", ["article_id"])
    op.execute(
        "CREATE INDEX ix_kb_article_chunk_search ON kb_article_chunk "
        f"USING gin (({_SEARCH_VECTOR}))"
    )

    op.create_table(
        "ai_request_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("retrieval_mode", sa.String(length=16), nullable=False),
        sa.Column("chunk_ids", sa.JSON(), nullable=False),
        sa.Column("cited_article_ids", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_request_log_organization_id", "ai_request_log", ["organization_id"]
    )
    op.create_index("ix_ai_request_log_created_at", "ai_request_log", ["created_at"])

    _chunk_existing_articles()


def _chunk_existing_articles() -> None:
    # Uses the splitter as it is at this revision; articles edited later are
    # re-chunked by the application.
    articles = op.get_bind().execute(
        sa.select(
            _article_table.c.id,
            _article_table.c.organization_id,
            _article_table.c.title,
            _article_table.c.body,
        ).where(_article_table.c.deleted_at.is_(None))
    )
    now = datetime.now(UTC)
    rows = [
        {
            "organization_id": organization_id,
            "article_id": article_id,
            "position": position,
            "heading": chunk.heading,
            "content": chunk.content,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        for article_id, organization_id, title, body in articles
        for position, chunk in enumerate(split_article(title, body))
    ]
    if rows:
        op.bulk_insert(_chunk_table, rows)


def downgrade() -> None:
    op.drop_index("ix_ai_request_log_created_at", table_name="ai_request_log")
    op.drop_index("ix_ai_request_log_organization_id", table_name="ai_request_log")
    op.drop_table("ai_request_log")
    op.execute("DROP INDEX ix_kb_article_chunk_search")
    op.drop_index("ix_kb_article_chunk_article_id", table_name="kb_article_chunk")
    op.drop_index("ix_kb_article_chunk_organization_id", table_name="kb_article_chunk")
    op.drop_table("kb_article_chunk")
