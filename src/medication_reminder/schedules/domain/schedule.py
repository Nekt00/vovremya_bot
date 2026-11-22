from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from medication_reminder.schedules.domain.rules import ScheduleRule
from medication_reminder.shared.timezones import validate_timezone


class InvalidStoredScheduleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredScheduleRule:
    id: UUID
    regimen_id: UUID
    rule: ScheduleRule
    timezone: str
    version: int
    active: bool
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "timezone", validate_timezone(self.timezone))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version <= 0:
            raise InvalidStoredScheduleError("Schedule version must be a positive integer")
        if not isinstance(self.active, bool):
            raise InvalidStoredScheduleError("Schedule active flag must be boolean")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != UTC.utcoffset(
            self.created_at
        ):
            raise InvalidStoredScheduleError("created_at must be timezone-aware and in UTC")
