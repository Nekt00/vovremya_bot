from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from medication_reminder.intake_events.domain.event import (
    IntakeEvent,
    IntakeEventStatus,
    InvalidIntakeEventError,
    InvalidIntakeTransitionError,
)


def make_event(**overrides: object) -> IntakeEvent:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    values: dict[str, object] = {
        "id": uuid4(),
        "regimen_id": uuid4(),
        "schedule_rule_id": uuid4(),
        "sequence_number": 1,
        "scheduled_at": datetime(2026, 10, 18, 9, tzinfo=UTC),
        "timezone": "Europe/Moscow",
        "status": IntakeEventStatus.SCHEDULED,
        "snoozed_until": None,
        "resolved_at": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return IntakeEvent(**values)  # type: ignore[arg-type]


def test_scheduled_event_can_be_marked_taken() -> None:
    event = make_event()
    resolved_at = event.updated_at + timedelta(minutes=5)

    taken = event.transition_to(IntakeEventStatus.TAKEN, at=resolved_at)

    assert taken.status is IntakeEventStatus.TAKEN
    assert taken.resolved_at == resolved_at
    assert taken.taken_at == resolved_at


def test_due_event_can_be_snoozed_then_returned_to_due() -> None:
    event = make_event().transition_to(
        IntakeEventStatus.DUE,
        at=datetime(2026, 10, 18, 9, tzinfo=UTC),
    )
    snoozed_at = event.updated_at + timedelta(minutes=1)
    snoozed_until = snoozed_at + timedelta(minutes=15)

    snoozed = event.transition_to(
        IntakeEventStatus.SNOOZED,
        at=snoozed_at,
        snoozed_until=snoozed_until,
    )
    due = snoozed.transition_to(IntakeEventStatus.DUE, at=snoozed_until)

    assert snoozed.snoozed_until == snoozed_until
    assert due.snoozed_until is None
    assert due.resolved_at is None


@pytest.mark.parametrize(
    "snoozed_until",
    [None, datetime(2026, 10, 18, 9, tzinfo=UTC), datetime(2026, 10, 18, 9, 2)],
)
def test_snooze_requires_future_aware_utc_time(snoozed_until: datetime | None) -> None:
    due = make_event().transition_to(
        IntakeEventStatus.DUE,
        at=datetime(2026, 10, 18, 9, tzinfo=UTC),
    )

    with pytest.raises(InvalidIntakeTransitionError):
        due.transition_to(
            IntakeEventStatus.SNOOZED,
            at=datetime(2026, 10, 18, 9, 1, tzinfo=UTC),
            snoozed_until=snoozed_until,
        )


@pytest.mark.parametrize(
    "status",
    [
        IntakeEventStatus.TAKEN,
        IntakeEventStatus.SKIPPED,
        IntakeEventStatus.MISSED,
        IntakeEventStatus.CANCELLED,
    ],
)
def test_terminal_event_requires_resolved_at(status: IntakeEventStatus) -> None:
    with pytest.raises(InvalidIntakeEventError, match="requires resolved_at"):
        make_event(status=status)


def test_terminal_status_cannot_transition() -> None:
    taken = make_event().transition_to(
        IntakeEventStatus.TAKEN,
        at=datetime(2026, 10, 18, 9, tzinfo=UTC),
    )

    with pytest.raises(InvalidIntakeTransitionError):
        taken.transition_to(
            IntakeEventStatus.SKIPPED,
            at=datetime(2026, 10, 18, 9, 1, tzinfo=UTC),
        )


@pytest.mark.parametrize("status", [IntakeEventStatus.MISSED, IntakeEventStatus.SKIPPED])
def test_missed_or_skipped_event_can_be_corrected_to_taken(
    status: IntakeEventStatus,
) -> None:
    resolved_at = datetime(2026, 10, 18, 9, tzinfo=UTC)
    event = make_event().transition_to(status, at=resolved_at)

    corrected = event.transition_to(
        IntakeEventStatus.TAKEN,
        at=resolved_at + timedelta(minutes=1),
    )

    assert corrected.status is IntakeEventStatus.TAKEN
    assert corrected.resolved_at == resolved_at + timedelta(minutes=1)
