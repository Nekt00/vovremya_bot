"""Create regimens table.

Revision ID: 20261017_02_regimens
Revises: 20261017_01_users
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_02_regimens"
down_revision: str | None = "20261017_01_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "regimens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("medication_name", sa.String(length=120), nullable=False),
        sa.Column("medication_form", sa.String(length=16), nullable=False),
        sa.Column("dose_amount", sa.Numeric(), nullable=False),
        sa.Column("dose_unit", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("total_intakes", sa.BigInteger(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("dose_amount > 0", name="ck_regimens_dose_amount_positive"),
        sa.CheckConstraint(
            "total_intakes IS NULL OR total_intakes > 0",
            name="ck_regimens_total_intakes_positive",
        ),
        sa.CheckConstraint(
            "NOT (total_intakes IS NOT NULL AND end_date IS NOT NULL)",
            name="ck_regimens_single_end_condition",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_regimens_end_date_not_before_start",
        ),
        sa.CheckConstraint(
            "medication_form IN ('tablet', 'capsule', 'injection', 'drops', 'other')",
            name="ck_regimens_medication_form",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed')",
            name="ck_regimens_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_regimens_user_status_created_at",
        "regimens",
        ["user_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_regimens_user_status_created_at", table_name="regimens")
    op.drop_table("regimens")
