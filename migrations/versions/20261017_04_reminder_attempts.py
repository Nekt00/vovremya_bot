"""Add reliable reminder delivery attempts.

Revision ID: 20261017_04_reminder_attempts
Revises: 20261017_03_schedules_events
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_04_reminder_attempts"
down_revision: str | None = "20261017_03_schedules_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminder_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("claim_token", sa.Uuid(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('claimed', 'sent', 'failed')", name="ck_reminder_attempts_status"
        ),
        sa.CheckConstraint("attempt_count > 0", name="ck_reminder_attempts_count_positive"),
        sa.ForeignKeyConstraint(["event_id"], ["intake_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reminder_attempts_event_scheduled",
        "reminder_attempts",
        ["event_id", "scheduled_for"],
    )
    op.create_index(
        "uq_reminder_attempts_idempotency_key",
        "reminder_attempts",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_reminder_attempts_idempotency_key", table_name="reminder_attempts")
    op.drop_index("ix_reminder_attempts_event_scheduled", table_name="reminder_attempts")
    op.drop_table("reminder_attempts")
