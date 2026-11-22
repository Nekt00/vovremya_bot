from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from medication_reminder.users.domain.validation import (
    validate_telegram_user_id,
    validate_timezone,
)


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    telegram_user_id: int
    timezone: str | None
    created_at: datetime
    updated_at: datetime
    reminder_repeat_minutes: int = 30
    reminders_enabled: bool = True

    def __post_init__(self) -> None:
        validate_telegram_user_id(self.telegram_user_id)
        if self.timezone is not None:
            validate_timezone(self.timezone)
        if self.reminder_repeat_minutes not in {15, 30, 60}:
            raise ValueError("reminder_repeat_minutes must be 15, 30, or 60")
        for field_name, value in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
                raise ValueError(f"{field_name} must be timezone-aware and in UTC")
