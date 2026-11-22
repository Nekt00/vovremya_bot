from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

MAX_MEDICATION_NAME_LENGTH = 120
MAX_DOSE_UNIT_LENGTH = 32


class InvalidRegimenError(ValueError):
    pass


class InvalidStatusTransitionError(ValueError):
    pass


class MedicationForm(StrEnum):
    TABLET = "tablet"
    CAPSULE = "capsule"
    INJECTION = "injection"
    DROPS = "drops"
    OTHER = "other"


class MealTiming(StrEnum):
    INDEPENDENT = "independent"
    BEFORE = "before"
    DURING = "during"
    AFTER = "after"


class RegimenStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


_ALLOWED_STATUS_TRANSITIONS: dict[RegimenStatus, frozenset[RegimenStatus]] = {
    RegimenStatus.ACTIVE: frozenset({RegimenStatus.PAUSED, RegimenStatus.COMPLETED}),
    RegimenStatus.PAUSED: frozenset({RegimenStatus.ACTIVE, RegimenStatus.COMPLETED}),
    RegimenStatus.COMPLETED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Regimen:
    id: UUID
    user_id: UUID
    medication_name: str
    medication_form: MedicationForm
    dose_amount: Decimal
    dose_unit: str
    start_date: date
    total_intakes: int | None
    end_date: date | None
    status: RegimenStatus
    created_at: datetime
    updated_at: datetime
    meal_timing: MealTiming = MealTiming.INDEPENDENT

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "medication_name",
            _normalize_text(self.medication_name, "Medication name", MAX_MEDICATION_NAME_LENGTH),
        )
        object.__setattr__(
            self,
            "dose_unit",
            _normalize_text(self.dose_unit, "Dose unit", MAX_DOSE_UNIT_LENGTH),
        )
        if not isinstance(self.medication_form, MedicationForm):
            raise InvalidRegimenError("Medication form is invalid")
        if (
            not isinstance(self.dose_amount, Decimal)
            or not self.dose_amount.is_finite()
            or self.dose_amount <= 0
        ):
            raise InvalidRegimenError("Dose amount must be a finite positive Decimal")
        if not isinstance(self.start_date, date) or isinstance(self.start_date, datetime):
            raise InvalidRegimenError("Start date must be a date")
        if self.total_intakes is not None and (
            isinstance(self.total_intakes, bool)
            or not isinstance(self.total_intakes, int)
            or self.total_intakes <= 0
        ):
            raise InvalidRegimenError("Total intakes must be a positive integer")
        if self.total_intakes is not None and self.end_date is not None:
            raise InvalidRegimenError("Total intakes and end date are mutually exclusive")
        if self.end_date is not None:
            if not isinstance(self.end_date, date) or isinstance(self.end_date, datetime):
                raise InvalidRegimenError("End date must be a date")
            if self.end_date < self.start_date:
                raise InvalidRegimenError("End date cannot be before start date")
        if not isinstance(self.status, RegimenStatus):
            raise InvalidRegimenError("Regimen status is invalid")
        if not isinstance(self.meal_timing, MealTiming):
            raise InvalidRegimenError("Meal timing is invalid")
        _validate_utc_timestamp(self.created_at, "created_at")
        _validate_utc_timestamp(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise InvalidRegimenError("updated_at cannot be before created_at")

    def transition_to(self, target: RegimenStatus, *, at: datetime) -> Regimen:
        if not isinstance(target, RegimenStatus):
            raise InvalidStatusTransitionError("Target regimen status is invalid")
        if target not in _ALLOWED_STATUS_TRANSITIONS[self.status]:
            raise InvalidStatusTransitionError(
                f"Cannot transition regimen from {self.status.value} to {target.value}"
            )
        _validate_utc_timestamp(at, "transition timestamp")
        if at < self.updated_at:
            raise InvalidStatusTransitionError("Transition timestamp cannot move backwards")
        return replace(self, status=target, updated_at=at)


def _normalize_text(value: str, label: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise InvalidRegimenError(f"{label} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise InvalidRegimenError(f"{label} cannot be empty")
    if len(normalized) > max_length:
        raise InvalidRegimenError(f"{label} cannot exceed {max_length} characters")
    if any(ord(character) < 32 for character in normalized):
        raise InvalidRegimenError(f"{label} cannot contain control characters")
    return normalized


def _validate_utc_timestamp(value: datetime, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidRegimenError(f"{label} must be timezone-aware and in UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise InvalidRegimenError(f"{label} must be timezone-aware and in UTC")
