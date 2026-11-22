from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.domain.event import (
    EventSource,
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
)
from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.schedules.domain.rules import DailyScheduleRule
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.schedules.infrastructure.repository import (
    SqlAlchemyScheduleMaterializationStore,
)


class FakeNestedTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class RecordingSession:
    def __init__(self) -> None:
        self.operations: list[tuple[str, tuple[str, ...]]] = []

    def begin_nested(self) -> FakeNestedTransaction:
        return FakeNestedTransaction()

    def add(self, model: object) -> None:
        self.operations.append(("add", (type(model).__name__,)))

    def add_all(self, models: list[Any]) -> None:
        self.operations.append(("add_all", tuple(type(model).__name__ for model in models)))

    async def flush(self) -> None:
        self.operations.append(("flush", ()))


@pytest.mark.asyncio
async def test_materialization_flushes_each_fk_parent_before_children() -> None:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    regimen_id = uuid4()
    schedule_id = uuid4()
    event_id = uuid4()
    schedule = StoredScheduleRule(
        id=schedule_id,
        regimen_id=regimen_id,
        rule=DailyScheduleRule((time(9),)),
        timezone="Europe/Moscow",
        version=1,
        active=True,
        created_at=now,
    )
    event = IntakeEvent(
        id=event_id,
        regimen_id=regimen_id,
        schedule_rule_id=schedule_id,
        sequence_number=1,
        scheduled_at=now,
        timezone="Europe/Moscow",
        status=IntakeEventStatus.SCHEDULED,
        snoozed_until=None,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )
    history = IntakeEventHistory(
        id=uuid4(),
        event_id=event_id,
        from_status=None,
        to_status=IntakeEventStatus.SCHEDULED,
        occurred_at=now,
        source=EventSource.SYSTEM,
    )
    session = RecordingSession()

    await SqlAlchemyScheduleMaterializationStore(cast(AsyncSession, session)).materialize(
        schedule,
        (event,),
        (history,),
        regimen=Regimen(
            id=regimen_id,
            user_id=uuid4(),
            medication_name="Препарат",
            medication_form=MedicationForm.TABLET,
            dose_amount=Decimal("1"),
            dose_unit="таблетка",
            start_date=now.date(),
            total_intakes=1,
            end_date=None,
            status=RegimenStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
    )

    assert session.operations == [
        ("add", ("ScheduleRuleModel",)),
        ("flush", ()),
        ("add_all", ("IntakeEventModel",)),
        ("flush", ()),
        ("add_all", ("IntakeEventHistoryModel",)),
        ("flush", ()),
    ]
