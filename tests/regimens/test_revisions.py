from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventHistory
from medication_reminder.regimens.application.revisions import (
    NoFutureEventsError,
    RegimenRevisionError,
    ReviseRegimen,
    ReviseRegimenCommand,
    RevisionContext,
)
from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.schedules.domain.rules import DailyScheduleRule, IntervalScheduleRule
from medication_reminder.schedules.domain.schedule import StoredScheduleRule


class FakeRevisionStore:
    def __init__(self, context: RevisionContext | None) -> None:
        self.context = context
        self.applied: (
            tuple[
                Regimen,
                StoredScheduleRule,
                tuple[IntakeEvent, ...],
                tuple[IntakeEventHistory, ...],
            ]
            | None
        ) = None

    async def get_context(
        self,
        user_id: UUID,
        regimen_id: UUID,
        *,
        effective_at: datetime,
    ) -> RevisionContext | None:
        del user_id, regimen_id, effective_at
        return self.context

    async def apply_revision(
        self,
        context: RevisionContext,
        revised_regimen: Regimen,
        schedule: StoredScheduleRule,
        events: tuple[IntakeEvent, ...],
        histories: tuple[IntakeEventHistory, ...],
        *,
        effective_at: datetime,
    ) -> None:
        del context, effective_at
        self.applied = revised_regimen, schedule, events, histories


def make_context(*, replaceable_count: int = 4) -> RevisionContext:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    regimen = Regimen(
        id=uuid4(),
        user_id=uuid4(),
        medication_name="D3",
        medication_form=MedicationForm.TABLET,
        dose_amount=Decimal("1"),
        dose_unit="таблетка",
        start_date=date(2026, 10, 1),
        total_intakes=10,
        end_date=None,
        status=RegimenStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    schedule = StoredScheduleRule(
        id=uuid4(),
        regimen_id=regimen.id,
        rule=DailyScheduleRule((time(9),)),
        timezone="Europe/Moscow",
        version=1,
        active=True,
        created_at=now,
    )
    return RevisionContext(regimen, schedule, replaceable_count)


@pytest.mark.asyncio
async def test_revision_creates_next_schedule_version_and_preserves_remaining_count() -> None:
    context = make_context()
    store = FakeRevisionStore(context)
    effective_at = datetime(2026, 10, 17, 8, tzinfo=UTC)
    rule = IntervalScheduleRule(3, (time(6),))

    result = await ReviseRegimen(store, clock=lambda: effective_at)(
        ReviseRegimenCommand(
            user_id=context.regimen.user_id,
            regimen_id=context.regimen.id,
            effective_at=effective_at,
            dose_amount=Decimal("2"),
            rule=rule,
        )
    )

    assert result.regimen.dose_amount == Decimal("2")
    assert result.schedule.version == 2
    assert result.schedule.rule == rule
    assert result.events_count == 4
    assert store.applied is not None
    assert all(event.scheduled_at > effective_at for event in store.applied[2])
    assert len(store.applied[3]) == 4


@pytest.mark.asyncio
async def test_revision_without_new_rule_keeps_current_rule() -> None:
    context = make_context(replaceable_count=2)
    store = FakeRevisionStore(context)
    effective_at = datetime(2026, 10, 17, 8, tzinfo=UTC)

    result = await ReviseRegimen(store, clock=lambda: effective_at)(
        ReviseRegimenCommand(
            user_id=context.regimen.user_id,
            regimen_id=context.regimen.id,
            effective_at=effective_at,
            dose_amount=Decimal("1.5"),
        )
    )

    assert result.schedule.rule == context.active_schedule.rule


@pytest.mark.asyncio
async def test_revision_rejects_course_without_future_events_before_applying() -> None:
    context = make_context(replaceable_count=0)
    store = FakeRevisionStore(context)

    with pytest.raises(NoFutureEventsError):
        await ReviseRegimen(store)(
            ReviseRegimenCommand(
                user_id=context.regimen.user_id,
                regimen_id=context.regimen.id,
                effective_at=datetime(2026, 10, 17, 8, tzinfo=UTC),
                dose_amount=Decimal("2"),
            )
        )

    assert store.applied is None


@pytest.mark.asyncio
async def test_revision_changes_remaining_intake_count() -> None:
    context = make_context(replaceable_count=4)
    context = RevisionContext(
        context.regimen,
        context.active_schedule,
        context.replaceable_count,
        resolved_count=6,
    )
    store = FakeRevisionStore(context)
    effective_at = datetime(2026, 10, 17, 8, tzinfo=UTC)

    result = await ReviseRegimen(store, clock=lambda: effective_at)(
        ReviseRegimenCommand(
            user_id=context.regimen.user_id,
            regimen_id=context.regimen.id,
            effective_at=effective_at,
            remaining_intakes=3,
        )
    )

    assert result.regimen.total_intakes == 9
    assert result.events_count == 3


@pytest.mark.asyncio
async def test_remaining_intakes_include_current_unresolved_intake() -> None:
    original = make_context(replaceable_count=4)
    context = RevisionContext(
        original.regimen,
        original.active_schedule,
        original.replaceable_count,
        resolved_count=6,
        pending_count=1,
    )
    store = FakeRevisionStore(context)
    effective_at = datetime(2026, 10, 17, 8, tzinfo=UTC)

    result = await ReviseRegimen(store, clock=lambda: effective_at)(
        ReviseRegimenCommand(
            user_id=context.regimen.user_id,
            regimen_id=context.regimen.id,
            effective_at=effective_at,
            remaining_intakes=3,
        )
    )

    assert result.regimen.total_intakes == 9
    assert result.events_count == 2


@pytest.mark.asyncio
async def test_remaining_intakes_cannot_discard_current_unresolved_intakes() -> None:
    original = make_context(replaceable_count=4)
    context = RevisionContext(
        original.regimen,
        original.active_schedule,
        original.replaceable_count,
        resolved_count=6,
        pending_count=2,
    )
    store = FakeRevisionStore(context)

    with pytest.raises(RegimenRevisionError):
        await ReviseRegimen(store)(
            ReviseRegimenCommand(
                user_id=context.regimen.user_id,
                regimen_id=context.regimen.id,
                effective_at=datetime(2026, 10, 17, 8, tzinfo=UTC),
                remaining_intakes=1,
            )
        )

    assert store.applied is None


@pytest.mark.asyncio
async def test_revision_changes_course_to_end_date() -> None:
    context = make_context(replaceable_count=4)
    store = FakeRevisionStore(context)
    effective_at = datetime(2026, 10, 17, 8, tzinfo=UTC)

    result = await ReviseRegimen(store, clock=lambda: effective_at)(
        ReviseRegimenCommand(
            user_id=context.regimen.user_id,
            regimen_id=context.regimen.id,
            effective_at=effective_at,
            end_date=date(2026, 10, 20),
        )
    )

    assert result.regimen.total_intakes is None
    assert result.regimen.end_date == date(2026, 10, 20)
    assert result.events_count == 3
