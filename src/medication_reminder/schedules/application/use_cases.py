from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from medication_reminder.intake_events.domain.event import (
    EventSource,
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
)
from medication_reminder.regimens.domain.regimen import Regimen
from medication_reminder.schedules.application.repositories import ScheduleMaterializationStore
from medication_reminder.schedules.domain.generator import generate_occurrences
from medication_reminder.schedules.domain.rules import ScheduleRule
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.shared.timezones import validate_timezone


@dataclass(frozen=True, slots=True)
class MaterializedSchedule:
    schedule: StoredScheduleRule
    events: tuple[IntakeEvent, ...]


class MaterializeSchedule:
    def __init__(
        self,
        store: ScheduleMaterializationStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    async def __call__(
        self,
        regimen: Regimen,
        rule: ScheduleRule,
        timezone: str,
        *,
        window_end: datetime,
        window_start: datetime | None = None,
        version: int = 1,
    ) -> MaterializedSchedule:
        confirmed_timezone = validate_timezone(timezone)
        now = self._clock()
        schedule = StoredScheduleRule(
            id=self._id_factory(),
            regimen_id=regimen.id,
            rule=rule,
            timezone=confirmed_timezone,
            version=version,
            active=True,
            created_at=now,
        )
        occurrences = generate_occurrences(
            regimen,
            rule,
            confirmed_timezone,
            window_end=window_end,
            window_start=window_start,
        )
        events = tuple(
            IntakeEvent(
                id=self._id_factory(),
                regimen_id=regimen.id,
                schedule_rule_id=schedule.id,
                sequence_number=occurrence.sequence_number,
                scheduled_at=occurrence.scheduled_at,
                timezone=confirmed_timezone,
                status=IntakeEventStatus.SCHEDULED,
                snoozed_until=None,
                resolved_at=None,
                created_at=now,
                updated_at=now,
            )
            for occurrence in occurrences
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
        await self._store.materialize(schedule, events, histories, regimen=regimen)
        return MaterializedSchedule(schedule=schedule, events=events)
