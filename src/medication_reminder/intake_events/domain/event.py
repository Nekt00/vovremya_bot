from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from medication_reminder.shared.timezones import validate_timezone


class InvalidIntakeEventError(ValueError):
    pass


class InvalidIntakeTransitionError(ValueError):
    pass


class IntakeEventStatus(StrEnum):
    SCHEDULED = "scheduled"
    DUE = "due"
    SNOOZED = "snoozed"
    TAKEN = "taken"
    SKIPPED = "skipped"
    MISSED = "missed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            IntakeEventStatus.TAKEN,
            IntakeEventStatus.SKIPPED,
            IntakeEventStatus.MISSED,
            IntakeEventStatus.CANCELLED,
        }


class EventSource(StrEnum):
    USER = "user"
    SYSTEM = "system"


_ALLOWED_TRANSITIONS: dict[IntakeEventStatus, frozenset[IntakeEventStatus]] = {
    IntakeEventStatus.SCHEDULED: frozenset(
        {
            IntakeEventStatus.DUE,
            IntakeEventStatus.TAKEN,
            IntakeEventStatus.SKIPPED,
            IntakeEventStatus.MISSED,
            IntakeEventStatus.CANCELLED,
        }
    ),
    IntakeEventStatus.DUE: frozenset(
        {
            IntakeEventStatus.SNOOZED,
            IntakeEventStatus.TAKEN,
            IntakeEventStatus.SKIPPED,
            IntakeEventStatus.MISSED,
            IntakeEventStatus.CANCELLED,
        }
    ),
    IntakeEventStatus.SNOOZED: frozenset(
        {
            IntakeEventStatus.DUE,
            IntakeEventStatus.TAKEN,
            IntakeEventStatus.SKIPPED,
            IntakeEventStatus.MISSED,
            IntakeEventStatus.CANCELLED,
        }
    ),
    IntakeEventStatus.TAKEN: frozenset({IntakeEventStatus.SCHEDULED}),
    IntakeEventStatus.SKIPPED: frozenset({IntakeEventStatus.TAKEN}),
    IntakeEventStatus.MISSED: frozenset({IntakeEventStatus.TAKEN}),
    IntakeEventStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class IntakeEvent:
    id: UUID
    regimen_id: UUID
    schedule_rule_id: UUID
    sequence_number: int
    scheduled_at: datetime
    timezone: str
    status: IntakeEventStatus
    snoozed_until: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def taken_at(self) -> datetime | None:
        """Return the actual confirmation time for a completed intake."""
        return self.resolved_at if self.status is IntakeEventStatus.TAKEN else None

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence_number, bool)
            or not isinstance(self.sequence_number, int)
            or self.sequence_number <= 0
        ):
            raise InvalidIntakeEventError("sequence_number must be a positive integer")
        object.__setattr__(self, "timezone", validate_timezone(self.timezone))
        for field_name, value in (
            ("scheduled_at", self.scheduled_at),
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            _validate_utc(value, field_name)
        if self.updated_at < self.created_at:
            raise InvalidIntakeEventError("updated_at cannot be before created_at")
        if not isinstance(self.status, IntakeEventStatus):
            raise InvalidIntakeEventError("status is invalid")

        if self.status is IntakeEventStatus.SNOOZED:
            if self.snoozed_until is None:
                raise InvalidIntakeEventError("snoozed event requires snoozed_until")
            _validate_utc(self.snoozed_until, "snoozed_until")
            if self.snoozed_until <= self.updated_at:
                raise InvalidIntakeEventError("snoozed_until must be after updated_at")
        elif self.snoozed_until is not None:
            raise InvalidIntakeEventError("only snoozed event can have snoozed_until")

        if self.status.is_terminal:
            if self.resolved_at is None:
                raise InvalidIntakeEventError("terminal event requires resolved_at")
            _validate_utc(self.resolved_at, "resolved_at")
            if self.resolved_at < self.created_at:
                raise InvalidIntakeEventError("resolved_at cannot be before created_at")
        elif self.resolved_at is not None:
            raise InvalidIntakeEventError("non-terminal event cannot have resolved_at")

    def transition_to(
        self,
        target: IntakeEventStatus,
        *,
        at: datetime,
        snoozed_until: datetime | None = None,
    ) -> IntakeEvent:
        if (
            not isinstance(target, IntakeEventStatus)
            or target not in _ALLOWED_TRANSITIONS[self.status]
        ):
            target_value = target.value if isinstance(target, IntakeEventStatus) else str(target)
            raise InvalidIntakeTransitionError(
                f"Cannot transition intake event from {self.status.value} to {target_value}"
            )
        _validate_transition_time(at, self.updated_at)
        if target is IntakeEventStatus.SNOOZED:
            if snoozed_until is None:
                raise InvalidIntakeTransitionError("snoozed transition requires snoozed_until")
            try:
                _validate_utc(snoozed_until, "snoozed_until")
            except InvalidIntakeEventError as error:
                raise InvalidIntakeTransitionError(str(error)) from error
            if snoozed_until <= at:
                raise InvalidIntakeTransitionError("snoozed_until must be in the future")
        elif snoozed_until is not None:
            raise InvalidIntakeTransitionError("snoozed_until is only valid for snoozed status")

        return replace(
            self,
            status=target,
            snoozed_until=snoozed_until,
            resolved_at=at if target.is_terminal else None,
            updated_at=at,
        )


@dataclass(frozen=True, slots=True)
class IntakeEventHistory:
    id: UUID
    event_id: UUID
    from_status: IntakeEventStatus | None
    to_status: IntakeEventStatus
    occurred_at: datetime
    source: EventSource

    def __post_init__(self) -> None:
        if not isinstance(self.to_status, IntakeEventStatus):
            raise InvalidIntakeEventError("history to_status is invalid")
        if self.from_status is None and self.to_status is not IntakeEventStatus.SCHEDULED:
            raise InvalidIntakeEventError("creation history must start in scheduled status")
        if self.from_status is not None and not isinstance(self.from_status, IntakeEventStatus):
            raise InvalidIntakeEventError("history from_status is invalid")
        if (
            self.from_status is not None
            and self.to_status not in _ALLOWED_TRANSITIONS[self.from_status]
        ):
            raise InvalidIntakeEventError(
                f"invalid history transition from {self.from_status.value} "
                f"to {self.to_status.value}"
            )
        if not isinstance(self.source, EventSource):
            raise InvalidIntakeEventError("history source is invalid")
        _validate_utc(self.occurred_at, "occurred_at")


def _validate_utc(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidIntakeEventError(f"{field_name} must be timezone-aware and in UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise InvalidIntakeEventError(f"{field_name} must be timezone-aware and in UTC")


def _validate_transition_time(at: datetime, current_updated_at: datetime) -> None:
    try:
        _validate_utc(at, "transition timestamp")
    except InvalidIntakeEventError as error:
        raise InvalidIntakeTransitionError(str(error)) from error
    if at < current_updated_at:
        raise InvalidIntakeTransitionError("transition timestamp cannot move backwards")
