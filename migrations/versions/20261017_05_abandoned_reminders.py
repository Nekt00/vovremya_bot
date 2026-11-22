"""Add terminal state for permanently undeliverable reminders.

Revision ID: 20261017_05_abandoned_reminders
Revises: 20261017_04_reminder_attempts
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261017_05_abandoned_reminders"
down_revision: str | None = "20261017_04_reminder_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_reminder_attempts_status",
        "reminder_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_reminder_attempts_status",
        "reminder_attempts",
        "status IN ('claimed', 'sent', 'failed', 'abandoned')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM reminder_attempts WHERE status = 'abandoned'")
    op.drop_constraint(
        "ck_reminder_attempts_status",
        "reminder_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_reminder_attempts_status",
        "reminder_attempts",
        "status IN ('claimed', 'sent', 'failed')",
    )
