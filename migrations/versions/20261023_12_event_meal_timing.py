"""Store meal timing on intake event snapshots.

Revision ID: 20261023_12_event_meal_timing
Revises: 20261023_11_family_roles
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_12_event_meal_timing"
down_revision: str | None = "20261023_11_family_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "intake_events",
        sa.Column(
            "meal_timing",
            sa.String(length=16),
            server_default="independent",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE intake_events AS event
        SET meal_timing = regimen.meal_timing
        FROM regimens AS regimen
        WHERE regimen.id = event.regimen_id
        """
    )
    op.create_check_constraint(
        "ck_intake_events_meal_timing",
        "intake_events",
        "meal_timing IN ('independent', 'before', 'during', 'after')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_intake_events_meal_timing", "intake_events", type_="check")
    op.drop_column("intake_events", "meal_timing")
