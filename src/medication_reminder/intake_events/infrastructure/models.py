from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class IntakeEventModel(Base):
    __tablename__ = "intake_events"
    __table_args__ = (
        CheckConstraint("sequence_number > 0", name="ck_intake_events_sequence_positive"),
        CheckConstraint("dose_amount > 0", name="ck_intake_events_dose_amount_positive"),
        CheckConstraint(
            "meal_timing IN ('independent', 'before', 'during', 'after')",
            name="ck_intake_events_meal_timing",
        ),
        CheckConstraint(
            "medication_form IN ('tablet', 'capsule', 'injection', 'drops', 'other')",
            name="ck_intake_events_medication_form",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'due', 'snoozed', 'taken', 'skipped', 'missed', 'cancelled')",
            name="ck_intake_events_status",
        ),
        CheckConstraint(
            "(status = 'snoozed') = (snoozed_until IS NOT NULL)",
            name="ck_intake_events_snooze_state",
        ),
        CheckConstraint(
            "status != 'snoozed' OR snoozed_until > updated_at",
            name="ck_intake_events_snooze_future",
        ),
        CheckConstraint(
            "(status IN ('taken', 'skipped', 'missed', 'cancelled')) = (resolved_at IS NOT NULL)",
            name="ck_intake_events_resolution_state",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at",
            name="ck_intake_events_resolution_time",
        ),
        ForeignKeyConstraint(
            ["schedule_rule_id", "regimen_id"],
            ["schedule_rules.id", "schedule_rules.regimen_id"],
            name="fk_intake_events_schedule_rule_regimen",
            ondelete="CASCADE",
        ),
        Index("uq_intake_events_rule_sequence", "schedule_rule_id", "sequence_number", unique=True),
        Index("ix_intake_events_status_scheduled_at", "status", "scheduled_at"),
        Index("ix_intake_events_regimen_sequence", "regimen_id", "sequence_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    regimen_id: Mapped[UUID] = mapped_column(
        ForeignKey("regimens.id", ondelete="CASCADE"),
        nullable=False,
    )
    schedule_rule_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    medication_name: Mapped[str] = mapped_column(String(120), nullable=False)
    medication_form: Mapped[str] = mapped_column(String(16), nullable=False)
    dose_amount: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)
    dose_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    meal_timing: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="independent"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class IntakeEventHistoryModel(Base):
    __tablename__ = "intake_event_history"
    __table_args__ = (
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('scheduled', 'due', 'snoozed', 'taken', 'skipped', 'missed', 'cancelled')",
            name="ck_intake_event_history_from_status",
        ),
        CheckConstraint(
            "to_status IN ('scheduled', 'due', 'snoozed', 'taken', 'skipped', 'missed', "
            "'cancelled')",
            name="ck_intake_event_history_to_status",
        ),
        CheckConstraint(
            "source IN ('user', 'system')",
            name="ck_intake_event_history_source",
        ),
        CheckConstraint(
            "from_status IS NOT NULL OR to_status = 'scheduled'",
            name="ck_intake_event_history_creation",
        ),
        Index("ix_intake_event_history_event_occurred", "event_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("intake_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
