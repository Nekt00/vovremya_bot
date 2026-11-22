"""Add meal timing instructions to regimens.

Revision ID: 20261023_10_meal_timing
Revises: 20261023_09_family_access
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_10_meal_timing"
down_revision: str | None = "20261023_09_family_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regimens",
        sa.Column(
            "meal_timing",
            sa.String(length=16),
            server_default="independent",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_regimens_meal_timing",
        "regimens",
        "meal_timing IN ('independent', 'before', 'during', 'after')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_regimens_meal_timing", "regimens", type_="check")
    op.drop_column("regimens", "meal_timing")
