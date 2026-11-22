"""Create versioned schedules and intake events.

Revision ID: 20261017_03_schedules_events
Revises: 20261017_02_regimens
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_03_schedules_events"
down_revision: str | None = "20261017_02_regimens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("regimen_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_schedule_rules_version_positive"),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_schedule_rules_payload_object",
        ),
        sa.CheckConstraint(
            "kind IN ('daily', 'interval', 'weekday')",
            name="ck_schedule_rules_kind",
        ),
        sa.ForeignKeyConstraint(["regimen_id"], ["regimens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "regimen_id",
            name="uq_schedule_rules_id_regimen",
        ),
        sa.UniqueConstraint(
            "regimen_id",
            "version",
            name="uq_schedule_rules_regimen_version",
        ),
    )
    op.create_index(
        "uq_schedule_rules_one_active_per_regimen",
        "schedule_rules",
        ["regimen_id"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE"),
    )

    op.create_table(
        "intake_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("regimen_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_rule_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            "sequence_number > 0",
            name="ck_intake_events_sequence_positive",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'due', 'snoozed', 'taken', 'skipped', 'missed', 'cancelled')",
            name="ck_intake_events_status",
        ),
        sa.CheckConstraint(
            "(status = 'snoozed') = (snoozed_until IS NOT NULL)",
            name="ck_intake_events_snooze_state",
        ),
        sa.CheckConstraint(
            "status != 'snoozed' OR snoozed_until > updated_at",
            name="ck_intake_events_snooze_future",
        ),
        sa.CheckConstraint(
            "(status IN ('taken', 'skipped', 'missed', 'cancelled')) = (resolved_at IS NOT NULL)",
            name="ck_intake_events_resolution_state",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at",
            name="ck_intake_events_resolution_time",
        ),
        sa.ForeignKeyConstraint(["regimen_id"], ["regimens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["schedule_rule_id", "regimen_id"],
            ["schedule_rules.id", "schedule_rules.regimen_id"],
            name="fk_intake_events_schedule_rule_regimen",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intake_events_regimen_sequence",
        "intake_events",
        ["regimen_id", "sequence_number"],
        unique=False,
    )
    op.create_index(
        "ix_intake_events_status_scheduled_at",
        "intake_events",
        ["status", "scheduled_at"],
        unique=False,
    )
    op.create_index(
        "uq_intake_events_rule_sequence",
        "intake_events",
        ["schedule_rule_id", "sequence_number"],
        unique=True,
    )

    op.create_table(
        "intake_event_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('scheduled', 'due', 'snoozed', 'taken', 'skipped', 'missed', 'cancelled')",
            name="ck_intake_event_history_from_status",
        ),
        sa.CheckConstraint(
            "to_status IN ('scheduled', 'due', 'snoozed', 'taken', 'skipped', 'missed', "
            "'cancelled')",
            name="ck_intake_event_history_to_status",
        ),
        sa.CheckConstraint(
            "source IN ('user', 'system')",
            name="ck_intake_event_history_source",
        ),
        sa.CheckConstraint(
            "from_status IS NOT NULL OR to_status = 'scheduled'",
            name="ck_intake_event_history_creation",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["intake_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intake_event_history_event_occurred",
        "intake_event_history",
        ["event_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_intake_event_history_event_occurred", table_name="intake_event_history")
    op.drop_table("intake_event_history")
    op.drop_index("uq_intake_events_rule_sequence", table_name="intake_events")
    op.drop_index("ix_intake_events_status_scheduled_at", table_name="intake_events")
    op.drop_index("ix_intake_events_regimen_sequence", table_name="intake_events")
    op.drop_table("intake_events")
    op.drop_index("uq_schedule_rules_one_active_per_regimen", table_name="schedule_rules")
    op.drop_table("schedule_rules")
