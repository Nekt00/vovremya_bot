from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from math import ceil
from typing import Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from medication_reminder.intake_events.domain.event import (
    EventSource,
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
)
from medication_reminder.regimens.domain.regimen import MealTiming, Regimen
from medication_reminder.schedules.domain.generator import generate_occurrences
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    ScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.schedules.domain.schedule import StoredScheduleRule

REVISION_OPEN_HORIZON_DAYS = 90


class RegimenRevisionError(RuntimeError):
    pass


class RegimenRevisionNotFoundError(RegimenRevisionError):
    pass


class RegimenRevisionConflictError(RegimenRevisionError):
    pass


class NoFutureEventsError(RegimenRevisionError):
    pass


class RemainingIntakesTooSmallError(RegimenRevisionError):
    def __init__(self, pending_count: int) -> None:
        super().__init__("Remaining intake count is less than unresolved intake count")
        self.pending_count = pending_count


@dataclass(frozen=True, slots=True)
class RevisionContext:
    regimen: Regimen
    active_schedule: StoredScheduleRule
    replaceable_count: int
    resolved_count: int = 0
    pending_count: int = 0


@dataclass(frozen=True, slots=True)
class ReviseRegimenCommand:
    user_id: UUID
    regimen_id: UUID
    effective_at: datetime
    dose_amount: Decimal | None = None
    meal_timing: MealTiming | None = None
    rule: ScheduleRule | None = None
    remaining_intakes: int | None = None
    end_date: date | None = None


@dataclass(frozen=True, slots=True)
class RevisedRegimen:
    regimen: Regimen
    schedule: StoredScheduleRule
    events_count: int


class RegimenRevisionStore(Protocol):
    async def get_context(
        self,
        user_id: UUID,
        regimen_id: UUID,
        *,
        effective_at: datetime,
    ) -> RevisionContext | None: ...

    async def apply_revision(
        self,
        context: RevisionContext,
        revised_regimen: Regimen,
        schedule: StoredScheduleRule,
        events: tuple[IntakeEvent, ...],
        histories: tuple[IntakeEventHistory, ...],
        *,
        effective_at: datetime,
    ) -> None: ...


class ReviseRegimen:
    def __init__(
        self,
        store: RegimenRevisionStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    async def __call__(self, command: ReviseRegimenCommand) -> RevisedRegimen:
        effective_at = _as_utc(command.effective_at)
        context = await self._store.get_context(
            command.user_id,
            command.regimen_id,
            effective_at=effective_at,
        )
        if context is None:
            raise RegimenRevisionNotFoundError("Active regimen was not found")
        if (
            context.replaceable_count == 0
            and command.remaining_intakes is None
            and command.end_date is None
        ):
            raise NoFutureEventsError("Regimen has no future intake events to revise")

        now = _as_utc(self._clock())
        dose_amount = (
            command.dose_amount if command.dose_amount is not None else context.regimen.dose_amount
        )
        meal_timing = command.meal_timing or context.regimen.meal_timing
        rule = command.rule if command.rule is not None else context.active_schedule.rule
        if command.remaining_intakes is not None and command.end_date is not None:
            raise RegimenRevisionError("Only one course ending can be changed at a time")
        if command.remaining_intakes is not None and command.remaining_intakes <= 0:
            raise RegimenRevisionError("Remaining intake count must be positive")
        if (
            command.remaining_intakes is not None
            and command.remaining_intakes < context.pending_count
        ):
            raise RemainingIntakesTooSmallError(context.pending_count)
        replacement_count = (
            command.remaining_intakes - context.pending_count
            if command.remaining_intakes is not None
            else context.replaceable_count
        )
        if command.end_date is not None:
            local_effective_date = effective_at.astimezone(
                ZoneInfo(context.active_schedule.timezone)
            ).date()
            if command.end_date < local_effective_date:
                raise RegimenRevisionError("End date cannot be in the past")
        revised_regimen = replace(
            context.regimen,
            dose_amount=dose_amount,
            meal_timing=meal_timing,
            total_intakes=(
                context.resolved_count + command.remaining_intakes
                if command.remaining_intakes is not None
                else None
                if command.end_date is not None
                else context.regimen.total_intakes
            ),
            end_date=(
                command.end_date
                if command.end_date is not None
                else None
                if command.remaining_intakes is not None
                else context.regimen.end_date
            ),
            updated_at=now,
        )
        if replacement_count:
            generation_regimen = _generation_regimen(
                revised_regimen,
                effective_at,
                timezone=context.active_schedule.timezone,
                replacement_count=replacement_count,
            )
            window_end = _revision_window_end(
                generation_regimen,
                rule,
                replacement_count,
                timezone=context.active_schedule.timezone,
            )
            occurrences = generate_occurrences(
                generation_regimen,
                rule,
                context.active_schedule.timezone,
                window_start=effective_at,
                window_end=window_end,
                count_before_window=False,
            )
        else:
            occurrences = ()
        if revised_regimen.total_intakes is not None and len(occurrences) != replacement_count:
            raise RegimenRevisionError("Could not preserve the remaining intake count")

        schedule = StoredScheduleRule(
            id=self._id_factory(),
            regimen_id=revised_regimen.id,
            rule=rule,
            timezone=context.active_schedule.timezone,
            version=context.active_schedule.version + 1,
            active=True,
            created_at=now,
        )
        events = tuple(
            IntakeEvent(
                id=self._id_factory(),
                regimen_id=revised_regimen.id,
                schedule_rule_id=schedule.id,
                sequence_number=item.sequence_number,
                scheduled_at=item.scheduled_at,
                timezone=schedule.timezone,
                status=IntakeEventStatus.SCHEDULED,
                snoozed_until=None,
                resolved_at=None,
                created_at=now,
                updated_at=now,
            )
            for item in occurrences
        )
        histories = tuple(
            IntakeEventHistory(
                id=self._id_factory(),
                event_id=event.id,
                from_status=None,
                to_status=IntakeEventStatus.SCHEDULED,
                occurred_at=now,
                source=EventSource.SYSTEM,
            )
            for event in events
        )
        await self._store.apply_revision(
            context,
            revised_regimen,
            schedule,
            events,
            histories,
            effective_at=effective_at,
        )
        return RevisedRegimen(revised_regimen, schedule, len(events))


def _generation_regimen(
    regimen: Regimen,
    effective_at: datetime,
    *,
    timezone: str,
    replacement_count: int,
) -> Regimen:
    local_date = effective_at.astimezone(ZoneInfo(timezone)).date()
    return replace(
        regimen,
        start_date=local_date,
        total_intakes=replacement_count if regimen.total_intakes is not None else None,
    )


def _revision_window_end(
    regimen: Regimen,
    rule: ScheduleRule,
    count: int,
    *,
    timezone: str,
) -> datetime:
    if regimen.end_date is not None:
        final_date = regimen.end_date
    elif regimen.total_intakes is not None:
        if isinstance(rule, WeeklyScheduleRule):
            intakes_per_week = sum(len(times) for _, times in rule.times_by_weekday)
            weeks = ceil(count / intakes_per_week)
            final_date = regimen.start_date + timedelta(days=weeks * 7 + 7)
            next_midnight = datetime.combine(
                final_date + timedelta(days=1),
                time.min,
                ZoneInfo(timezone),
            )
            return (next_midnight - timedelta(microseconds=1)).astimezone(UTC)
        times_per_day = len(rule.times)
        matching_days = ceil(count / times_per_day)
        if isinstance(rule, DailyScheduleRule):
            days = matching_days + 1
        elif isinstance(rule, IntervalScheduleRule):
            days = matching_days * rule.every_days + 1
        elif isinstance(rule, WeekdayScheduleRule):
            days = (matching_days + 1) * 7
        else:
            raise TypeError(f"Unsupported schedule rule: {type(rule).__name__}")
        final_date = regimen.start_date + timedelta(days=days)
    else:
        final_date = regimen.start_date + timedelta(days=REVISION_OPEN_HORIZON_DAYS - 1)
    next_midnight = datetime.combine(
        final_date + timedelta(days=1),
        time.min,
        ZoneInfo(timezone),
    )
    return (next_midnight - timedelta(microseconds=1)).astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RegimenRevisionError("Timestamp must be timezone-aware")
    return value.astimezone(UTC)
