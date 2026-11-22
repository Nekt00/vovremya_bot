from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class ReminderAttemptModel(Base):
    __tablename__ = "reminder_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('claimed', 'sent', 'failed', 'abandoned')",
            name="ck_reminder_attempts_status",
        ),
        CheckConstraint("attempt_count > 0", name="ck_reminder_attempts_count_positive"),
        Index("uq_reminder_attempts_idempotency_key", "idempotency_key", unique=True),
        Index("ix_reminder_attempts_event_scheduled", "event_id", "scheduled_for"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("intake_events.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    claim_token: Mapped[UUID] = mapped_column(nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
