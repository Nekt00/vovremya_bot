from datetime import datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class MedicationSetModel(Base):
    __tablename__ = "medication_sets"
    __table_args__ = (
        CheckConstraint("window_start < window_end", name="ck_medication_sets_window_order"),
        UniqueConstraint("user_id", "name", name="uq_medication_sets_user_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[time] = mapped_column(Time(), nullable=False)
    window_end: Mapped[time] = mapped_column(Time(), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MedicationSetMemberModel(Base):
    __tablename__ = "medication_set_members"
    __table_args__ = (UniqueConstraint("regimen_id", name="uq_medication_set_members_regimen"),)

    set_id: Mapped[UUID] = mapped_column(
        ForeignKey("medication_sets.id", ondelete="CASCADE"), primary_key=True
    )
    regimen_id: Mapped[UUID] = mapped_column(
        ForeignKey("regimens.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
