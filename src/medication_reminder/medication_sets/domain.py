from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID

from medication_reminder.regimens.domain.regimen import Regimen
from medication_reminder.shared.timezones import validate_timezone


class InvalidMedicationSetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MedicationSet:
    id: UUID
    user_id: UUID
    name: str
    window_start: time
    window_end: time
    timezone: str
    active: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        normalized = " ".join(self.name.split())
        if not normalized or len(normalized) > 64:
            raise InvalidMedicationSetError("Set name must contain from 1 to 64 characters")
        object.__setattr__(self, "name", normalized)
        for value in (self.window_start, self.window_end):
            if value.tzinfo is not None or value.second or value.microsecond:
                raise InvalidMedicationSetError("Set times must use local minute precision")
        if self.window_start >= self.window_end:
            raise InvalidMedicationSetError("Set window end must be after its start")
        object.__setattr__(self, "timezone", validate_timezone(self.timezone))


@dataclass(frozen=True, slots=True)
class MedicationSetDetails:
    medication_set: MedicationSet
    regimens: tuple[Regimen, ...]
