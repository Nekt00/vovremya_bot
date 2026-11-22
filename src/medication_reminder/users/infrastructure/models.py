from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("telegram_user_id > 0", name="ck_users_telegram_user_id_positive"),
        CheckConstraint(
            "reminder_repeat_minutes IN (15, 30, 60)",
            name="ck_users_reminder_repeat_minutes",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reminder_repeat_minutes: Mapped[int] = mapped_column(
        Integer,
        server_default=text("30"),
        nullable=False,
    )
    reminders_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
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
