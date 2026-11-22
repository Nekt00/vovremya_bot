from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class ScheduleRuleModel(Base):
    __tablename__ = "schedule_rules"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_schedule_rules_version_positive"),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_schedule_rules_payload_object",
        ),
        CheckConstraint(
            "kind IN ('daily', 'interval', 'weekday')",
            name="ck_schedule_rules_kind",
        ),
        UniqueConstraint("regimen_id", "version", name="uq_schedule_rules_regimen_version"),
        UniqueConstraint("id", "regimen_id", name="uq_schedule_rules_id_regimen"),
        Index(
            "uq_schedule_rules_one_active_per_regimen",
            "regimen_id",
            unique=True,
            postgresql_where=text("active IS TRUE"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    regimen_id: Mapped[UUID] = mapped_column(
        ForeignKey("regimens.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
