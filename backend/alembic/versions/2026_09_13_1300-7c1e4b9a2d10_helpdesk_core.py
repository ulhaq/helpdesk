"""helpdesk: tickets, contacts, support site and knowledge base

Revision ID: 7c1e4b9a2d10
Revises: 2c3b2ee136dc
Create Date: 2026-09-13 13:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "7c1e4b9a2d10"
down_revision: str | None = "2c3b2ee136dc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_billing_plan_setting_table = sa.table(
    "billing_plan_setting",
    sa.column("plan_id", sa.Integer),
    sa.column("key", sa.String),
    sa.column("value", sa.Integer),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
    sa.column("deleted_at", sa.DateTime),
)

# Per seeded plan (plan ids from the initial migration); None = unlimited.
_PLAN_LIMITS = {
    "tickets_per_month": {1: 50, 2: 500, 3: 5000, 4: None},
    "kb_articles": {1: 10, 2: 50, 3: 500, 4: None},
}


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "contact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_organization_id", "contact", ["organization_id"])
    op.create_index("ix_contact_email", "contact", ["email"])

    op.create_table(
        "ticket",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contact.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "number", name="uq_ticket_organization_number"
        ),
    )
    op.create_index("ix_ticket_organization_id", "ticket", ["organization_id"])
    op.create_index("ix_ticket_status", "ticket", ["status"])
    op.create_index("ix_ticket_contact_id", "ticket", ["contact_id"])
    op.create_index("ix_ticket_assignee_id", "ticket", ["assignee_id"])

    op.create_table(
        "ticket_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("author_type", sa.String(length=16), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("author_contact_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["author_contact_id"], ["contact.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_message_organization_id", "ticket_message", ["organization_id"]
    )
    op.create_index("ix_ticket_message_ticket_id", "ticket_message", ["ticket_id"])

    op.create_table(
        "support_site",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("brand_color", sa.String(length=7), nullable=False),
        sa.Column("greeting", sa.String(length=255), nullable=True),
        sa.Column("widget_enabled", sa.Boolean(), nullable=False),
        sa.Column("help_center_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_support_site_organization_id",
        "support_site",
        ["organization_id"],
        unique=True,
    )
    op.create_index("ix_support_site_slug", "support_site", ["slug"], unique=True)

    op.create_table(
        "kb_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_category_organization_id", "kb_category", ["organization_id"])
    op.create_index("ix_kb_category_slug", "kb_category", ["slug"])

    op.create_table(
        "kb_article",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["kb_category.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["author_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_article_organization_id", "kb_article", ["organization_id"])
    op.create_index("ix_kb_article_category_id", "kb_article", ["category_id"])
    op.create_index("ix_kb_article_slug", "kb_article", ["slug"])
    op.create_index("ix_kb_article_status", "kb_article", ["status"])

    now = datetime.now(UTC)
    op.bulk_insert(
        _billing_plan_setting_table,
        [
            {
                "plan_id": plan_id,
                "key": key,
                "value": value,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
            for key, limits in _PLAN_LIMITS.items()
            for plan_id, value in limits.items()
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.delete(_billing_plan_setting_table).where(
            _billing_plan_setting_table.c.key.in_(list(_PLAN_LIMITS))
        )
    )
    op.drop_index("ix_kb_article_status", table_name="kb_article")
    op.drop_index("ix_kb_article_slug", table_name="kb_article")
    op.drop_index("ix_kb_article_category_id", table_name="kb_article")
    op.drop_index("ix_kb_article_organization_id", table_name="kb_article")
    op.drop_table("kb_article")
    op.drop_index("ix_kb_category_slug", table_name="kb_category")
    op.drop_index("ix_kb_category_organization_id", table_name="kb_category")
    op.drop_table("kb_category")
    op.drop_index("ix_support_site_slug", table_name="support_site")
    op.drop_index("ix_support_site_organization_id", table_name="support_site")
    op.drop_table("support_site")
    op.drop_index("ix_ticket_message_ticket_id", table_name="ticket_message")
    op.drop_index("ix_ticket_message_organization_id", table_name="ticket_message")
    op.drop_table("ticket_message")
    op.drop_index("ix_ticket_assignee_id", table_name="ticket")
    op.drop_index("ix_ticket_contact_id", table_name="ticket")
    op.drop_index("ix_ticket_status", table_name="ticket")
    op.drop_index("ix_ticket_organization_id", table_name="ticket")
    op.drop_table("ticket")
    op.drop_index("ix_contact_email", table_name="contact")
    op.drop_index("ix_contact_organization_id", table_name="contact")
    op.drop_table("contact")
