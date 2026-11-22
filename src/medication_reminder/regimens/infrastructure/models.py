from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class RegimenModel(Base):
    __tablename__ = "regimens"
    __table_args__ = (
        CheckConstraint("dose_amount > 0", name="ck_regimens_dose_amount_positive"),
        CheckConstraint(
            "total_intakes IS NULL OR total_intakes > 0",
            name="ck_regimens_total_intakes_positive",
        ),
        CheckConstraint(
            "NOT (total_intakes IS NOT NULL AND end_date IS NOT NULL)",
            name="ck_regimens_single_end_condition",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_regimens_end_date_not_before_start",
        ),
        CheckConstraint(
            "medication_form IN ('tablet', 'capsule', 'injection', 'drops', 'other')",
            name="ck_regimens_medication_form",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'completed')",
            name="ck_regimens_status",
        ),
        CheckConstraint(
            "meal_timing IN ('independent', 'before', 'during', 'after')",
            name="ck_regimens_meal_timing",
        ),
        Index("ix_regimens_user_status_created_at", "user_id", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    medication_name: Mapped[str] = mapped_column(String(120), nullable=False)
    medication_form: Mapped[str] = mapped_column(String(16), nullable=False)
    dose_amount: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)
    dose_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_intakes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    meal_timing: Mapped[str] = mapped_column(
        String(16), nullable=False, default="independent", server_default="independent"
    )
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
