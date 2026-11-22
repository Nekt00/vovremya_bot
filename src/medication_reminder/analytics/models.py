from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class UserActivityModel(Base):
    __tablename__ = "user_activity"
    __table_args__ = (Index("ix_user_activity_date", "activity_date"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    activity_date: Mapped[date] = mapped_column(Date, primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
