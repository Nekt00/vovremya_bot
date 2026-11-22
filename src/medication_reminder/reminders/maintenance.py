from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.medication_sets.models import (
    MedicationSetMemberModel,
    MedicationSetModel,
)
from medication_reminder.regimens.domain.regimen import (
    MealTiming,
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.reminders.models import ReminderAttemptModel
from medication_reminder.schedules.domain.generator import generate_occurrences
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel
from medication_reminder.schedules.infrastructure.repository import _schedule_to_domain

PENDING_STATUSES = ("scheduled", "due", "snoozed")
TERMINAL_STATUSES = ("taken", "skipped", "missed", "cancelled")


async def cleanup_terminal_reminder_attempts(
    session: AsyncSession,
    *,
    before: datetime,
) -> int:
    """Delete old delivery records only after their intake event is terminal."""
    deleted_ids = await session.scalars(
        delete(ReminderAttemptModel)
        .where(
            ReminderAttemptModel.updated_at < _as_utc(before),
            ReminderAttemptModel.event_id.in_(
                select(IntakeEventModel.id).where(IntakeEventModel.status.in_(TERMINAL_STATUSES))
            ),
        )
        .returning(ReminderAttemptModel.id)
    )
    return len(list(deleted_ids))


async def expire_overdue_events(session: AsyncSession, *, now: datetime) -> int:
    """Resolve pending events after their local reminder deadline.

    Set members use the set window end. Standalone reminders remain actionable until
    the end of their local calendar day.
    """
    current = _as_utc(now)
    active_set = exists(
        select(MedicationSetMemberModel.regimen_id)
        .join(MedicationSetModel, MedicationSetModel.id == MedicationSetMemberModel.set_id)
        .where(
            MedicationSetMemberModel.regimen_id == IntakeEventModel.regimen_id,
            MedicationSetModel.active.is_(True),
        )
    )
    standalone = list(
        (
            await session.scalars(
                select(IntakeEventModel)
                .join(RegimenModel, RegimenModel.id == IntakeEventModel.regimen_id)
                .where(
                    RegimenModel.status == RegimenStatus.ACTIVE.value,
                    IntakeEventModel.status.in_(PENDING_STATUSES),
                    IntakeEventModel.scheduled_at <= current,
                    ~active_set,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    expired: list[IntakeEventModel] = []
    for event in standalone:
        zone = ZoneInfo(event.timezone)
        local_date = _as_utc(event.scheduled_at).astimezone(zone).date()
        deadline = datetime.combine(local_date + timedelta(days=1), time.min, zone).astimezone(UTC)
        if current >= deadline:
            expired.append(event)

    set_rows = (
        await session.execute(
            select(IntakeEventModel, MedicationSetModel)
            .join(
                MedicationSetMemberModel,
                MedicationSetMemberModel.regimen_id == IntakeEventModel.regimen_id,
            )
            .join(MedicationSetModel, MedicationSetModel.id == MedicationSetMemberModel.set_id)
            .join(RegimenModel, RegimenModel.id == IntakeEventModel.regimen_id)
            .where(
                MedicationSetModel.active.is_(True),
                RegimenModel.status == RegimenStatus.ACTIVE.value,
                IntakeEventModel.status.in_(PENDING_STATUSES),
                IntakeEventModel.scheduled_at <= current,
            )
            .with_for_update(skip_locked=True, of=IntakeEventModel)
        )
    ).all()
    seen = {event.id for event in expired}
    for event, medication_set in set_rows:
        zone = ZoneInfo(medication_set.timezone)
        local_date = _as_utc(event.scheduled_at).astimezone(zone).date()
        deadline = datetime.combine(local_date, medication_set.window_end, zone).astimezone(UTC)
        if current >= deadline and event.id not in seen:
            expired.append(event)
            seen.add(event.id)

    for event in expired:
        previous = event.status
        event.status = "missed"
        event.snoozed_until = None
        event.resolved_at = current
        event.updated_at = current
        session.add(
            IntakeEventHistoryModel(
                id=uuid4(),
                event_id=event.id,
                from_status=previous,
                to_status="missed",
                occurred_at=current,
                source="system",
            )
        )
    if expired:
        await session.flush()
    return len(expired)


async def extend_open_ended_schedules(
    session: AsyncSession,
    *,
    now: datetime,
    horizon_days: int,
) -> int:
    """Idempotently keep open-ended active schedules materialized ahead."""
    current = _as_utc(now)
    latest_event_at = (
        select(func.max(IntakeEventModel.scheduled_at))
        .where(IntakeEventModel.schedule_rule_id == ScheduleRuleModel.id)
        .correlate(ScheduleRuleModel)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(RegimenModel, ScheduleRuleModel, latest_event_at)
            .join(
                ScheduleRuleModel,
                (ScheduleRuleModel.regimen_id == RegimenModel.id)
                & ScheduleRuleModel.active.is_(True),
            )
            .where(
                RegimenModel.status == RegimenStatus.ACTIVE.value,
                RegimenModel.total_intakes.is_(None),
                RegimenModel.end_date.is_(None),
            )
            .with_for_update(of=ScheduleRuleModel, skip_locked=True)
        )
    ).all()
    created = 0
    new_events: list[IntakeEventModel] = []
    new_histories: list[IntakeEventHistoryModel] = []
    for regimen_model, schedule_model, latest_at in rows:
        schedule = _schedule_to_domain(schedule_model)
        zone = ZoneInfo(schedule.timezone)
        target_local_date = current.astimezone(zone).date() + timedelta(days=horizon_days)
        target_end = (
            datetime.combine(target_local_date + timedelta(days=1), time.min, zone)
            - timedelta(microseconds=1)
        ).astimezone(UTC)
        latest = _as_utc(latest_at) if latest_at is not None else None
        if latest is not None and latest >= target_end - timedelta(days=1):
            continue
        regimen = _regimen_to_domain(regimen_model)
        occurrences = generate_occurrences(
            regimen,
            schedule.rule,
            schedule.timezone,
            window_start=(latest + timedelta(microseconds=1)) if latest is not None else None,
            window_end=target_end,
        )
        timestamp = current
        for occurrence in occurrences:
            event = IntakeEventModel(
                id=uuid4(),
                regimen_id=regimen.id,
                schedule_rule_id=schedule.id,
                sequence_number=occurrence.sequence_number,
                scheduled_at=occurrence.scheduled_at,
                timezone=schedule.timezone,
                medication_name=regimen.medication_name,
                medication_form=regimen.medication_form.value,
                dose_amount=regimen.dose_amount,
                dose_unit=regimen.dose_unit,
                meal_timing=regimen.meal_timing.value,
                status="scheduled",
                snoozed_until=None,
                resolved_at=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
            new_events.append(event)
            new_histories.append(
                IntakeEventHistoryModel(
                    id=uuid4(),
                    event_id=event.id,
                    from_status=None,
                    to_status="scheduled",
                    occurred_at=timestamp,
                    source="system",
                )
            )
            created += 1
    if created:
        session.add_all(new_events)
        await session.flush()
        session.add_all(new_histories)
        await session.flush()
    return created


def _regimen_to_domain(model: RegimenModel) -> Regimen:
    return Regimen(
        id=model.id,
        user_id=model.user_id,
        medication_name=model.medication_name,
        medication_form=MedicationForm(model.medication_form),
        dose_amount=model.dose_amount,
        dose_unit=model.dose_unit,
        start_date=model.start_date,
        total_intakes=model.total_intakes,
        end_date=model.end_date,
        status=RegimenStatus(model.status),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
        meal_timing=MealTiming(model.meal_timing),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)
