"""Create medication sets.

Revision ID: 20261017_07_medication_sets
Revises: 20261017_06_event_snapshot
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_07_medication_sets"
down_revision: str | None = "20261017_06_event_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medication_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("window_start", sa.Time(), nullable=False),
        sa.Column("window_end", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint("window_start < window_end", name="ck_medication_sets_window_order"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_medication_sets_user_name"),
    )
    op.create_table(
        "medication_set_members",
        sa.Column("set_id", sa.Uuid(), nullable=False),
        sa.Column("regimen_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["regimen_id"], ["regimens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_id"], ["medication_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("set_id", "regimen_id"),
        sa.UniqueConstraint("regimen_id", name="uq_medication_set_members_regimen"),
    )


def downgrade() -> None:
    op.drop_table("medication_set_members")
    op.drop_table("medication_sets")
