from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.application.repositories import (
    IntakeEventDetailsRepository,
    IntakeEventRepository,
)
from medication_reminder.intake_events.domain.event import (
    EventSource,
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
    InvalidIntakeTransitionError,
)


class IntakeEventNotFoundError(LookupError):
    pass


class IntakeEventUpdateConflictError(RuntimeError):
    pass


class InvalidIntakeEventWindowError(ValueError):
    pass


class TransitionIntakeEvent:
    def __init__(
        self,
        repository: IntakeEventRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory

    async def __call__(
        self,
        user_id: UUID,
        event_id: UUID,
        target_status: IntakeEventStatus,
        *,
        source: EventSource,
        snoozed_until: datetime | None = None,
    ) -> IntakeEvent:
        current = await self._repository.get_for_user(event_id, user_id)
        if current is None:
            raise IntakeEventNotFoundError(f"Intake event {event_id} was not found")
        if current.status is target_status:
            return current

        if target_status is IntakeEventStatus.SNOOZED and snoozed_until is not None:
            deadline_getter = getattr(self._repository, "deadline_for_event", None)
            deadline = (
                await deadline_getter(event_id, user_id) if deadline_getter is not None else None
            )
            if deadline is None:
                zone = ZoneInfo(current.timezone)
                local_date = current.scheduled_at.astimezone(zone).date()
                deadline = datetime.combine(
                    local_date + timedelta(days=1),
                    time.min,
                    zone,
                ).astimezone(UTC)
            if snoozed_until >= deadline:
                raise InvalidIntakeTransitionError(
                    "Нельзя отложить приём за пределы окна напоминания"
                )

        transitioned = current.transition_to(
            target_status,
            at=self._clock(),
            snoozed_until=snoozed_until,
        )
        history = IntakeEventHistory(
            id=self._id_factory(),
            event_id=event_id,
            from_status=current.status,
            to_status=target_status,
            occurred_at=transitioned.updated_at,
            source=source,
        )
        updated = await self._repository.transition(
            transitioned,
            user_id=user_id,
            expected_status=current.status,
            history=history,
        )
        if updated is not None:
            return updated

        latest = await self._repository.get_for_user(event_id, user_id)
        if latest is not None and target_status.is_terminal and latest.status is target_status:
            return latest
        raise IntakeEventUpdateConflictError("Intake event was changed concurrently")


class ListUserIntakeEvents:
    def __init__(self, repository: IntakeEventRepository) -> None:
        self._repository = repository

    async def __call__(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEvent]:
        start_utc = _as_utc(window_start, "window_start")
        end_utc = _as_utc(window_end, "window_end")
        if start_utc > end_utc:
            raise InvalidIntakeEventWindowError("window_start cannot be after window_end")
        return await self._repository.list_for_user(
            user_id,
            window_start=start_utc,
            window_end=end_utc,
        )


class ListUserIntakeEventDetails:
    def __init__(self, repository: IntakeEventDetailsRepository) -> None:
        self._repository = repository

    async def __call__(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEventDetails]:
        start_utc = _as_utc(window_start, "window_start")
        end_utc = _as_utc(window_end, "window_end")
        if start_utc >= end_utc:
            raise InvalidIntakeEventWindowError("window_start must be before window_end")
        return await self._repository.list_details_for_user(
            user_id,
            window_start=start_utc,
            window_end=end_utc,
        )


def _as_utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidIntakeEventWindowError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)
