"""helpdesk: ai_requests_per_month plan limits

Revision ID: 3f6b8e1c2a47
Revises: 7c1e4b9a2d10
Create Date: 2026-09-14 10:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "3f6b8e1c2a47"
down_revision: str | None = "7c1e4b9a2d10"
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

_KEY = "ai_requests_per_month"
# Per seeded plan (plan ids from the initial migration); None = unlimited.
_LIMITS = {1: 50, 2: 1000, 3: 10000, 4: None}


def upgrade() -> None:
    now = datetime.now(UTC)
    op.bulk_insert(
        _billing_plan_setting_table,
        [
            {
                "plan_id": plan_id,
                "key": _KEY,
                "value": value,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
            for plan_id, value in _LIMITS.items()
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.delete(_billing_plan_setting_table).where(
            _billing_plan_setting_table.c.key == _KEY
        )
    )
