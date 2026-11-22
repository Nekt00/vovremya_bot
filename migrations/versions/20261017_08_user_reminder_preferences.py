"""Add user reminder preferences.

Revision ID: 20261017_08_user_preferences
Revises: 20261017_07_medication_sets
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_08_user_preferences"
down_revision: str | None = "20261017_07_medication_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "reminder_repeat_minutes",
            sa.Integer(),
            server_default=sa.text("30"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "reminders_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_reminder_repeat_minutes",
        "users",
        "reminder_repeat_minutes IN (15, 30, 60)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_reminder_repeat_minutes", "users", type_="check")
    op.drop_column("users", "reminders_enabled")
    op.drop_column("users", "reminder_repeat_minutes")
