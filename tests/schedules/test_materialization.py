from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventHistory
from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.schedules.application.repositories import ScheduleMaterializationStore
from medication_reminder.schedules.application.use_cases import MaterializeSchedule
from medication_reminder.schedules.domain.rules import DailyScheduleRule, IntervalScheduleRule
from medication_reminder.schedules.domain.schedule import StoredScheduleRule


class InMemoryScheduleStore:
    def __init__(self) -> None:
        self.schedule: StoredScheduleRule | None = None
        self.events: tuple[IntakeEvent, ...] = ()
        self.histories: tuple[IntakeEventHistory, ...] = ()

    async def materialize(
        self,
        schedule: StoredScheduleRule,
        events: tuple[IntakeEvent, ...],
        histories: tuple[IntakeEventHistory, ...],
        *,
        regimen: Regimen,
    ) -> None:
        del regimen
        self.schedule = schedule
        self.events = events
        self.histories = histories

    async def get_active(self, regimen_id: UUID) -> StoredScheduleRule | None:
        if self.schedule is not None and self.schedule.regimen_id == regimen_id:
            return self.schedule
        return None


def assert_schedule_store(store: ScheduleMaterializationStore) -> None:
    assert store is not None


def make_regimen(*, total_intakes: int) -> Regimen:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    return Regimen(
        id=uuid4(),
        user_id=uuid4(),
        medication_name="Injection X",
        medication_form=MedicationForm.INJECTION,
        dose_amount=Decimal("1"),
        dose_unit="mg",
        start_date=date(2026, 10, 20),
        total_intakes=total_intakes,
        end_date=None,
        status=RegimenStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_materializes_35_interval_events_and_creation_histories() -> None:
    store = InMemoryScheduleStore()
    assert_schedule_store(store)
    now = datetime(2026, 10, 17, 9, tzinfo=UTC)

    result = await MaterializeSchedule(store, clock=lambda: now)(
        make_regimen(total_intakes=35),
        IntervalScheduleRule(3, (time(10),)),
        "Europe/Moscow",
        window_end=datetime(2027, 12, 31, 23, 59, tzinfo=UTC),
    )

    assert result.schedule.version == 1
    assert result.schedule.active is True
    assert len(result.events) == 35
    assert [event.sequence_number for event in result.events] == list(range(1, 36))
    assert len(store.histories) == 35
    assert all(history.from_status is None for history in store.histories)
    assert all(event.timezone == "Europe/Moscow" for event in result.events)


@pytest.mark.asyncio
async def test_materialization_respects_daily_total_across_multiple_times() -> None:
    store = InMemoryScheduleStore()

    result = await MaterializeSchedule(store)(
        make_regimen(total_intakes=3),
        DailyScheduleRule((time(9), time(21))),
        "UTC",
        window_end=datetime(2026, 10, 30, 23, 59, tzinfo=UTC),
    )

    assert len(result.events) == 3
    assert [event.scheduled_at.time() for event in result.events] == [
        time(9),
        time(21),
        time(9),
    ]
