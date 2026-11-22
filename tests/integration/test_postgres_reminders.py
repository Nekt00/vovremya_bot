from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.application.use_cases import TransitionIntakeEvent
from medication_reminder.intake_events.domain.event import EventSource, IntakeEventStatus
from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.intake_events.infrastructure.repository import (
    SqlAlchemyIntakeEventRepository,
)
from medication_reminder.medication_sets.models import (
    MedicationSetMemberModel,
    MedicationSetModel,
)
from medication_reminder.medication_sets.repository import SqlAlchemyMedicationSetRepository
from medication_reminder.regimens.application.revisions import (
    ReviseRegimen,
    ReviseRegimenCommand,
)
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.regimens.infrastructure.revision_store import (
    SqlAlchemyRegimenRevisionStore,
)
from medication_reminder.reminders.maintenance import expire_overdue_events
from medication_reminder.reminders.models import ReminderAttemptModel
from medication_reminder.reminders.repository import SqlAlchemyReminderRepository
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel
from medication_reminder.users.infrastructure.models import UserModel

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_morning_take_all_excludes_evening_and_can_be_undone(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 27, 8, tzinfo=UTC)
    user_id = await _add_user(db_session, 6001)
    morning_id, morning_rule = await _add_regimen(db_session, user_id)
    evening_id, evening_rule = await _add_regimen(db_session, user_id)
    morning_set, evening_set = uuid4(), uuid4()
    for set_id, name, start, end in (
        (morning_set, "Утро", time(6), time(12)),
        (evening_set, "Вечер", time(18), time(23)),
    ):
        db_session.add(
            MedicationSetModel(
                id=set_id,
                user_id=user_id,
                name=name,
                window_start=start,
                window_end=end,
                timezone="UTC",
                active=True,
                created_at=now,
                updated_at=now,
            )
        )
    await db_session.flush()
    db_session.add_all(
        [
            MedicationSetMemberModel(set_id=morning_set, regimen_id=morning_id),
            MedicationSetMemberModel(set_id=evening_set, regimen_id=evening_id),
        ]
    )
    morning = _event(
        morning_id,
        morning_rule,
        sequence=1,
        scheduled_at=now.replace(hour=6),
        status="scheduled",
        updated_at=now,
    )
    later_morning = _event(
        morning_id,
        morning_rule,
        sequence=2,
        scheduled_at=now.replace(hour=10),
        status="scheduled",
        updated_at=now,
    )
    evening = _event(
        evening_id,
        evening_rule,
        sequence=1,
        scheduled_at=now.replace(hour=18),
        status="scheduled",
        updated_at=now,
    )
    db_session.add_all([morning, later_morning, evening])
    await db_session.flush()
    repository = SqlAlchemyMedicationSetRepository(db_session)
    assert await repository.take_all(user_id, morning_set, now.date(), occurred_at=now) == 1
    await db_session.refresh(evening)
    await db_session.refresh(later_morning)
    assert evening.status == "scheduled"
    assert later_morning.status == "scheduled"

    undo = await TransitionIntakeEvent(
        SqlAlchemyIntakeEventRepository(db_session), clock=lambda: now + timedelta(seconds=1)
    )(user_id, morning.id, IntakeEventStatus.SCHEDULED, source=EventSource.USER)
    assert undo.taken_at is None
    assert undo.resolved_at is None
    assert (
        await repository.take_all(
            user_id, morning_set, now.date(), occurred_at=now + timedelta(seconds=2)
        )
        == 1
    )
    transition = TransitionIntakeEvent(
        SqlAlchemyIntakeEventRepository(db_session), clock=lambda: now + timedelta(seconds=3)
    )
    await transition(user_id, evening.id, IntakeEventStatus.TAKEN, source=EventSource.USER)
    await transition(user_id, evening.id, IntakeEventStatus.SCHEDULED, source=EventSource.USER)
    reminders = SqlAlchemyReminderRepository(db_session)
    morning_claims = await reminders.claim_set_batch(
        now=now + timedelta(seconds=4),
        batch_size=10,
        retry_interval=timedelta(minutes=1),
        claim_timeout=timedelta(minutes=5),
    )
    assert all(claim.set_id != evening_set for claim in morning_claims)
    await db_session.refresh(evening)
    assert evening.status == "scheduled"
    evening_claims = await reminders.claim_set_batch(
        now=now.replace(hour=18),
        batch_size=10,
        retry_interval=timedelta(minutes=1),
        claim_timeout=timedelta(minutes=5),
    )
    assert len(evening_claims) == 1
    assert evening_claims[0].set_id == evening_set
    assert [item.event_id for item in evening_claims[0].items] == [evening.id]


async def _add_user(session: AsyncSession, telegram_id: int, repeat_minutes: int = 30) -> UUID:
    user_id = uuid4()
    session.add(
        UserModel(
            id=user_id,
            telegram_user_id=telegram_id,
            timezone="UTC",
            reminder_repeat_minutes=repeat_minutes,
            reminders_enabled=True,
        )
    )
    await session.flush()
    return user_id


async def _add_regimen(
    session: AsyncSession,
    user_id: UUID,
    *,
    status: str = "active",
    total_intakes: int = 6,
) -> tuple[UUID, UUID]:
    regimen_id = uuid4()
    schedule_id = uuid4()
    created_at = datetime(2026, 10, 1, tzinfo=UTC)
    session.add(
        RegimenModel(
            id=regimen_id,
            user_id=user_id,
            medication_name="D3",
            medication_form="tablet",
            dose_amount=Decimal("1"),
            dose_unit="таблетка",
            start_date=datetime(2026, 10, 1, tzinfo=UTC).date(),
            total_intakes=total_intakes,
            end_date=None,
            status=status,
            meal_timing="independent",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.add(
        ScheduleRuleModel(
            id=schedule_id,
            regimen_id=regimen_id,
            kind="daily",
            payload={"times": ["09:00"]},
            timezone="UTC",
            version=1,
            active=True,
            created_at=created_at,
        )
    )
    await session.flush()
    return regimen_id, schedule_id


def _event(
    regimen_id: UUID,
    schedule_id: UUID,
    *,
    sequence: int,
    scheduled_at: datetime,
    status: str,
    updated_at: datetime,
    meal_timing: str = "independent",
) -> IntakeEventModel:
    terminal = status in {"taken", "skipped", "missed", "cancelled"}
    return IntakeEventModel(
        id=uuid4(),
        regimen_id=regimen_id,
        schedule_rule_id=schedule_id,
        sequence_number=sequence,
        scheduled_at=scheduled_at,
        timezone="UTC",
        medication_name="D3",
        medication_form="tablet",
        dose_amount=Decimal("1"),
        dose_unit="таблетка",
        meal_timing=meal_timing,
        status=status,
        snoozed_until=None,
        resolved_at=updated_at if terminal else None,
        created_at=updated_at - timedelta(days=1),
        updated_at=updated_at,
    )


@pytest.mark.asyncio
async def test_expiry_ignores_paused_regimens(db_session: AsyncSession) -> None:
    now = datetime(2026, 10, 18, 0, 1, tzinfo=UTC)
    user_id = await _add_user(db_session, 1001)
    active_id, active_schedule = await _add_regimen(db_session, user_id)
    paused_id, paused_schedule = await _add_regimen(db_session, user_id, status="paused")
    active_event = _event(
        active_id,
        active_schedule,
        sequence=1,
        scheduled_at=now - timedelta(hours=15),
        status="scheduled",
        updated_at=now - timedelta(hours=15),
    )
    paused_event = _event(
        paused_id,
        paused_schedule,
        sequence=1,
        scheduled_at=now - timedelta(hours=15),
        status="scheduled",
        updated_at=now - timedelta(hours=15),
    )
    db_session.add_all((active_event, paused_event))
    await db_session.flush()

    assert await expire_overdue_events(db_session, now=now) == 1
    await db_session.refresh(active_event)
    await db_session.refresh(paused_event)
    assert active_event.status == "missed"
    assert paused_event.status == "scheduled"


@pytest.mark.asyncio
async def test_claim_uses_each_users_repeat_interval(db_session: AsyncSession) -> None:
    now = datetime(2026, 10, 17, 10, tzinfo=UTC)
    short_user = await _add_user(db_session, 2001, repeat_minutes=15)
    long_user = await _add_user(db_session, 2002, repeat_minutes=60)
    short_regimen, short_schedule = await _add_regimen(db_session, short_user)
    long_regimen, long_schedule = await _add_regimen(db_session, long_user)
    short_event = _event(
        short_regimen,
        short_schedule,
        sequence=1,
        scheduled_at=now - timedelta(hours=1),
        status="due",
        updated_at=now - timedelta(hours=1),
    )
    long_event = _event(
        long_regimen,
        long_schedule,
        sequence=1,
        scheduled_at=now - timedelta(hours=1),
        status="due",
        updated_at=now - timedelta(hours=1),
    )
    db_session.add_all((short_event, long_event))
    await db_session.flush()
    for event in (short_event, long_event):
        db_session.add(
            ReminderAttemptModel(
                id=uuid4(),
                event_id=event.id,
                idempotency_key=f"previous:{event.id}",
                scheduled_for=now - timedelta(minutes=20),
                status="sent",
                claim_token=uuid4(),
                claimed_at=now - timedelta(minutes=20),
                sent_at=now - timedelta(minutes=20),
                attempt_count=1,
                updated_at=now - timedelta(minutes=20),
            )
        )
    await db_session.flush()

    claimed = await SqlAlchemyReminderRepository(db_session).claim_batch(
        now=now,
        batch_size=10,
        retry_interval=timedelta(minutes=1),
        claim_timeout=timedelta(minutes=5),
    )

    assert [item.telegram_user_id for item in claimed] == [2001]


@pytest.mark.asyncio
async def test_revision_remaining_count_includes_due_event(db_session: AsyncSession) -> None:
    now = datetime(2026, 10, 17, 12, tzinfo=UTC)
    user_id = await _add_user(db_session, 3001)
    regimen_id, schedule_id = await _add_regimen(db_session, user_id)
    events = [
        _event(
            regimen_id,
            schedule_id,
            sequence=1,
            scheduled_at=now - timedelta(days=1),
            status="taken",
            updated_at=now - timedelta(hours=12),
        ),
        _event(
            regimen_id,
            schedule_id,
            sequence=2,
            scheduled_at=now - timedelta(hours=1),
            status="due",
            updated_at=now - timedelta(hours=1),
        ),
        *(
            _event(
                regimen_id,
                schedule_id,
                sequence=index + 3,
                scheduled_at=now + timedelta(days=index + 1),
                status="scheduled",
                updated_at=now - timedelta(days=1),
            )
            for index in range(4)
        ),
    ]
    db_session.add_all(events)
    await db_session.flush()

    result = await ReviseRegimen(
        SqlAlchemyRegimenRevisionStore(db_session),
        clock=lambda: now,
    )(
        ReviseRegimenCommand(
            user_id=user_id,
            regimen_id=regimen_id,
            effective_at=now,
            remaining_intakes=3,
        )
    )

    assert result.regimen.total_intakes == 4
    assert result.events_count == 2
    scheduled_count = await db_session.scalar(
        select(func.count(IntakeEventModel.id)).where(
            IntakeEventModel.regimen_id == regimen_id,
            IntakeEventModel.status == "scheduled",
        )
    )
    cancelled_count = await db_session.scalar(
        select(func.count(IntakeEventModel.id)).where(
            IntakeEventModel.regimen_id == regimen_id,
            IntakeEventModel.status == "cancelled",
        )
    )
    assert scheduled_count == 2
    assert cancelled_count == 4


@pytest.mark.asyncio
async def test_event_keeps_meal_timing_snapshot(db_session: AsyncSession) -> None:
    now = datetime(2026, 10, 23, 12, tzinfo=UTC)
    user_id = await _add_user(db_session, 4001)
    regimen_id, schedule_id = await _add_regimen(db_session, user_id)
    regimen = await db_session.get(RegimenModel, regimen_id)
    assert regimen is not None
    regimen.meal_timing = "after"
    event = _event(
        regimen_id,
        schedule_id,
        sequence=1,
        scheduled_at=now - timedelta(hours=1),
        status="due",
        updated_at=now - timedelta(hours=1),
        meal_timing="before",
    )
    db_session.add(event)
    await db_session.flush()

    details = await SqlAlchemyIntakeEventRepository(db_session).list_details_for_user(
        user_id,
        window_start=now - timedelta(days=1),
        window_end=now + timedelta(days=1),
    )
    claimed = await SqlAlchemyReminderRepository(db_session).claim_batch(
        now=now,
        batch_size=1,
        retry_interval=timedelta(minutes=1),
        claim_timeout=timedelta(minutes=5),
    )

    assert details[0].meal_timing.value == "before"
    assert claimed[0].meal_timing.value == "before"


@pytest.mark.asyncio
async def test_set_reminder_only_claims_events_inside_its_window(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 23, 6, 30, tzinfo=UTC)
    user_id = await _add_user(db_session, 5001)
    regimen_id, schedule_id = await _add_regimen(db_session, user_id)
    set_id = uuid4()
    db_session.add(
        MedicationSetModel(
            id=set_id,
            user_id=user_id,
            name="Утро",
            window_start=time(6),
            window_end=time(12),
            timezone="UTC",
            active=True,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()
    db_session.add(MedicationSetMemberModel(set_id=set_id, regimen_id=regimen_id))
    morning_event = _event(
        regimen_id,
        schedule_id,
        sequence=1,
        scheduled_at=now.replace(minute=0),
        status="scheduled",
        updated_at=now,
    )
    evening_event = _event(
        regimen_id,
        schedule_id,
        sequence=2,
        scheduled_at=now.replace(hour=18, minute=0),
        status="scheduled",
        updated_at=now,
    )
    db_session.add_all((morning_event, evening_event))
    await db_session.flush()

    claimed = await SqlAlchemyReminderRepository(db_session).claim_set_batch(
        now=now,
        batch_size=10,
        retry_interval=timedelta(minutes=1),
        claim_timeout=timedelta(minutes=5),
    )

    assert len(claimed) == 1
    assert [item.event_id for item in claimed[0].items] == [morning_event.id]
    await db_session.refresh(evening_event)
    assert evening_event.status == "scheduled"


@pytest.mark.asyncio
async def test_take_set_is_limited_to_its_window(db_session: AsyncSession) -> None:
    morning = datetime(2026, 10, 23, 8, tzinfo=UTC)
    user_id = await _add_user(db_session, 5002)
    regimen_id, schedule_id = await _add_regimen(db_session, user_id)
    set_id = uuid4()
    db_session.add(
        MedicationSetModel(
            id=set_id,
            user_id=user_id,
            name="Вечер",
            window_start=time(18),
            window_end=time(23),
            timezone="UTC",
            active=True,
            created_at=morning,
            updated_at=morning,
        )
    )
    await db_session.flush()
    db_session.add(MedicationSetMemberModel(set_id=set_id, regimen_id=regimen_id))
    morning_event = _event(
        regimen_id,
        schedule_id,
        sequence=1,
        scheduled_at=morning,
        status="scheduled",
        updated_at=morning,
    )
    evening_event = _event(
        regimen_id,
        schedule_id,
        sequence=2,
        scheduled_at=morning + timedelta(hours=10),
        status="scheduled",
        updated_at=morning,
    )
    db_session.add_all((morning_event, evening_event))
    await db_session.flush()
    repository = SqlAlchemyMedicationSetRepository(db_session)

    assert await repository.take_all(user_id, set_id, morning.date(), occurred_at=morning) == 0
    assert (
        await repository.take_all(
            user_id,
            set_id,
            morning.date(),
            occurred_at=morning + timedelta(hours=10),
        )
        == 1
    )
    await db_session.refresh(morning_event)
    await db_session.refresh(evening_event)
    assert morning_event.status == "scheduled"
    assert evening_event.status == "taken"
