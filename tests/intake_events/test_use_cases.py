from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from medication_reminder.intake_events.application.repositories import IntakeEventRepository
from medication_reminder.intake_events.application.use_cases import (
    IntakeEventNotFoundError,
    IntakeEventUpdateConflictError,
    ListUserIntakeEvents,
    TransitionIntakeEvent,
)
from medication_reminder.intake_events.domain.event import (
    EventSource,
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
)


class InMemoryIntakeEventRepository:
    def __init__(self) -> None:
        self.events: dict[UUID, IntakeEvent] = {}
        self.owners: dict[UUID, UUID] = {}
        self.histories: list[IntakeEventHistory] = []
        self.force_conflict = False

    async def get_for_user(self, event_id: UUID, user_id: UUID) -> IntakeEvent | None:
        if self.owners.get(event_id) != user_id:
            return None
        return self.events.get(event_id)

    async def transition(
        self,
        event: IntakeEvent,
        *,
        user_id: UUID,
        expected_status: IntakeEventStatus,
        history: IntakeEventHistory,
    ) -> IntakeEvent | None:
        current = await self.get_for_user(event.id, user_id)
        if self.force_conflict or current is None or current.status is not expected_status:
            return None
        self.events[event.id] = event
        self.histories.append(history)
        return event

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEvent]:
        return sorted(
            (
                event
                for event_id, event in self.events.items()
                if self.owners[event_id] == user_id
                and window_start <= event.scheduled_at <= window_end
            ),
            key=lambda event: event.scheduled_at,
        )


def assert_intake_repository(repository: IntakeEventRepository) -> None:
    assert repository is not None


def make_event() -> IntakeEvent:
    created_at = datetime(2026, 10, 17, 8, tzinfo=UTC)
    return IntakeEvent(
        id=uuid4(),
        regimen_id=uuid4(),
        schedule_rule_id=uuid4(),
        sequence_number=1,
        scheduled_at=datetime(2026, 10, 18, 9, tzinfo=UTC),
        timezone="Europe/Moscow",
        status=IntakeEventStatus.SCHEDULED,
        snoozed_until=None,
        resolved_at=None,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.mark.asyncio
async def test_transition_is_scoped_to_owner() -> None:
    repository = InMemoryIntakeEventRepository()
    assert_intake_repository(repository)
    event = make_event()
    repository.events[event.id] = event
    repository.owners[event.id] = uuid4()

    with pytest.raises(IntakeEventNotFoundError):
        await TransitionIntakeEvent(repository)(
            uuid4(),
            event.id,
            IntakeEventStatus.TAKEN,
            source=EventSource.USER,
        )


@pytest.mark.asyncio
async def test_terminal_action_is_idempotent_without_extra_history() -> None:
    repository = InMemoryIntakeEventRepository()
    user_id = uuid4()
    event = make_event()
    repository.events[event.id] = event
    repository.owners[event.id] = user_id
    now = datetime(2026, 10, 18, 9, tzinfo=UTC)
    use_case = TransitionIntakeEvent(repository, clock=lambda: now)

    first = await use_case(
        user_id,
        event.id,
        IntakeEventStatus.TAKEN,
        source=EventSource.USER,
    )
    second = await use_case(
        user_id,
        event.id,
        IntakeEventStatus.TAKEN,
        source=EventSource.USER,
    )

    assert first == second
    assert len(repository.histories) == 1


@pytest.mark.asyncio
async def test_undo_clears_actual_time_and_allows_retaking_with_audit_history() -> None:
    repository = InMemoryIntakeEventRepository()
    user_id = uuid4()
    event = make_event()
    repository.events[event.id] = event
    repository.owners[event.id] = user_id
    now = datetime(2026, 10, 18, 9, tzinfo=UTC)
    use_case = TransitionIntakeEvent(repository, clock=lambda: now)
    await use_case(user_id, event.id, IntakeEventStatus.TAKEN, source=EventSource.USER)
    now += timedelta(minutes=1)
    undone = await use_case(user_id, event.id, IntakeEventStatus.SCHEDULED, source=EventSource.USER)
    assert undone.taken_at is None
    assert undone.resolved_at is None
    now += timedelta(minutes=1)
    retaken = await use_case(user_id, event.id, IntakeEventStatus.TAKEN, source=EventSource.USER)
    assert retaken.taken_at == now
    assert [(row.from_status, row.to_status) for row in repository.histories] == [
        (IntakeEventStatus.SCHEDULED, IntakeEventStatus.TAKEN),
        (IntakeEventStatus.TAKEN, IntakeEventStatus.SCHEDULED),
        (IntakeEventStatus.SCHEDULED, IntakeEventStatus.TAKEN),
    ]


@pytest.mark.asyncio
async def test_missed_event_can_be_corrected_to_taken_with_history() -> None:
    repository = InMemoryIntakeEventRepository()
    user_id = uuid4()
    missed_at = datetime(2026, 10, 18, 10, tzinfo=UTC)
    event = make_event().transition_to(IntakeEventStatus.MISSED, at=missed_at)
    repository.events[event.id] = event
    repository.owners[event.id] = user_id

    corrected = await TransitionIntakeEvent(
        repository,
        clock=lambda: missed_at + timedelta(minutes=1),
    )(
        user_id,
        event.id,
        IntakeEventStatus.TAKEN,
        source=EventSource.USER,
    )

    assert corrected.status is IntakeEventStatus.TAKEN
    assert repository.histories[0].from_status is IntakeEventStatus.MISSED
    assert repository.histories[0].to_status is IntakeEventStatus.TAKEN


@pytest.mark.asyncio
async def test_snooze_action_is_idempotent_without_extending_delay() -> None:
    repository = InMemoryIntakeEventRepository()
    user_id = uuid4()
    event = replace(make_event(), status=IntakeEventStatus.DUE)
    repository.events[event.id] = event
    repository.owners[event.id] = user_id
    now = datetime(2026, 10, 18, 9, tzinfo=UTC)
    use_case = TransitionIntakeEvent(repository, clock=lambda: now)
    snoozed_until = now + timedelta(minutes=30)

    first = await use_case(
        user_id,
        event.id,
        IntakeEventStatus.SNOOZED,
        source=EventSource.USER,
        snoozed_until=snoozed_until,
    )
    second = await use_case(
        user_id,
        event.id,
        IntakeEventStatus.SNOOZED,
        source=EventSource.USER,
        snoozed_until=now + timedelta(minutes=60),
    )

    assert second == first
    assert second.snoozed_until == snoozed_until
    assert len(repository.histories) == 1


@pytest.mark.asyncio
async def test_transition_detects_optimistic_conflict() -> None:
    repository = InMemoryIntakeEventRepository()
    user_id = uuid4()
    event = make_event()
    repository.events[event.id] = event
    repository.owners[event.id] = user_id
    repository.force_conflict = True
    transition_time = datetime(2026, 10, 18, 9, tzinfo=UTC)

    with pytest.raises(IntakeEventUpdateConflictError):
        await TransitionIntakeEvent(repository, clock=lambda: transition_time)(
            user_id,
            event.id,
            IntakeEventStatus.TAKEN,
            source=EventSource.USER,
        )


@pytest.mark.asyncio
async def test_list_events_filters_owner_and_inclusive_utc_window() -> None:
    repository = InMemoryIntakeEventRepository()
    user_id = uuid4()
    first = make_event()
    second = replace(first, id=uuid4(), scheduled_at=first.scheduled_at + timedelta(hours=1))
    other = replace(first, id=uuid4())
    for event, owner in ((first, user_id), (second, user_id), (other, uuid4())):
        repository.events[event.id] = event
        repository.owners[event.id] = owner

    result = await ListUserIntakeEvents(repository)(
        user_id,
        window_start=first.scheduled_at,
        window_end=second.scheduled_at,
    )

    assert result == [first, second]
