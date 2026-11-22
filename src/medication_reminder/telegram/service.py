from datetime import UTC, datetime, time, timedelta
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardMarkup

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.application.use_cases import (
    IntakeEventNotFoundError,
    ListUserIntakeEventDetails,
    TransitionIntakeEvent,
)
from medication_reminder.intake_events.application.windows import (
    current_window_intakes,
    next_today_intake,
)
from medication_reminder.intake_events.domain.event import EventSource, IntakeEventStatus
from medication_reminder.medication_sets.application import ListMedicationSets
from medication_reminder.telegram.callbacks import EventAction, EventCallback
from medication_reminder.telegram.clock import Clock, local_day_utc_bounds
from medication_reminder.telegram.formatting import format_intake_detail, format_today
from medication_reminder.users.application.repositories import (
    ReminderPreferencesRepository,
    UserDataRepository,
    UserRepository,
)
from medication_reminder.users.application.use_cases import GetOrCreateUser, UpdateUserTimezone
from medication_reminder.users.domain.user import User


class TimezoneRequiredError(RuntimeError):
    pass


class TelegramApplicationService:
    def __init__(
        self,
        user_repository: UserRepository,
        list_event_details: ListUserIntakeEventDetails,
        transition_event: TransitionIntakeEvent,
        *,
        clock: Clock,
        list_medication_sets: ListMedicationSets | None = None,
    ) -> None:
        self._preferences_repository = cast(ReminderPreferencesRepository, user_repository)
        self._user_data_repository = cast(UserDataRepository, user_repository)
        self._get_or_create_user = GetOrCreateUser(user_repository)
        self._update_timezone = UpdateUserTimezone(user_repository)
        self._list_event_details = list_event_details
        self._transition_event = transition_event
        self._clock = clock
        self._list_medication_sets = list_medication_sets

    async def ensure_user(self, telegram_user_id: int) -> User:
        return await self._get_or_create_user(telegram_user_id)

    async def update_timezone(self, telegram_user_id: int, timezone: str) -> User:
        await self._get_or_create_user(telegram_user_id)
        return await self._update_timezone(telegram_user_id, timezone)

    async def update_reminder_preferences(
        self,
        telegram_user_id: int,
        *,
        repeat_minutes: int | None = None,
        enabled: bool | None = None,
    ) -> User:
        if repeat_minutes is not None and repeat_minutes not in {15, 30, 60}:
            raise ValueError("Unsupported repeat interval")
        await self._get_or_create_user(telegram_user_id)
        user = await self._preferences_repository.update_reminder_preferences(
            telegram_user_id,
            repeat_minutes=repeat_minutes,
            enabled=enabled,
        )
        if user is None:
            raise RuntimeError("User disappeared while updating reminder preferences")
        return user

    async def export_user_data(self, telegram_user_id: int) -> dict[str, object]:
        data = await self._user_data_repository.export_user_data(telegram_user_id)
        return data or {"user": {"telegram_user_id": telegram_user_id}}

    async def delete_user_data(self, telegram_user_id: int) -> bool:
        return await self._user_data_repository.delete_user_data(telegram_user_id)

    async def today(
        self, telegram_user_id: int, *, current_window: bool = True
    ) -> tuple[User, list[IntakeEventDetails]]:
        user = await self._get_or_create_user(telegram_user_id)
        if user.timezone is None:
            raise TimezoneRequiredError
        window_start, window_end = local_day_utc_bounds(self._clock(), user.timezone)
        details = await self._list_event_details(
            user.id,
            window_start=window_start,
            window_end=window_end,
        )
        if current_window:
            medication_sets = (
                await self._list_medication_sets(user.id)
                if self._list_medication_sets is not None
                else []
            )
            details = current_window_intakes(details, medication_sets, now=self._clock())
        return user, details

    async def today_screen(self, telegram_user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
        user, details = await self.today(telegram_user_id, current_window=False)
        if user.timezone is None:
            raise TimezoneRequiredError
        medication_sets = (
            await self._list_medication_sets(user.id) if self._list_medication_sets else []
        )
        now = self._clock()
        visible = current_window_intakes(details, medication_sets, now=now)
        current_regimens = {item.event.regimen_id for item in visible}
        labels = [
            f"{item.medication_set.name} · {item.medication_set.window_start:%H:%M}"
            f"–{item.medication_set.window_end:%H:%M}"
            for item in medication_sets
            if item.medication_set.active
            and any(regimen.id in current_regimens for regimen in item.regimens)
        ]
        return format_today(
            visible,
            user.timezone,
            upcoming=next_today_intake(details, medication_sets, now=now),
            window_label=" / ".join(labels) or None,
        )

    async def history(
        self,
        telegram_user_id: int,
        *,
        days: int,
    ) -> tuple[User, list[IntakeEventDetails]]:
        if days not in {7, 30}:
            raise ValueError("History period must be 7 or 30 days")
        user = await self._get_or_create_user(telegram_user_id)
        if user.timezone is None:
            raise TimezoneRequiredError
        zone = ZoneInfo(user.timezone)
        local_today = self._clock().astimezone(zone).date()
        local_start = datetime.combine(
            local_today - timedelta(days=days - 1),
            time.min,
            zone,
        )
        local_end = datetime.combine(local_today + timedelta(days=1), time.min, zone)
        details = await self._list_event_details(
            user.id,
            window_start=local_start.astimezone(UTC),
            window_end=local_end.astimezone(UTC),
        )
        return user, details

    async def intake_screen(
        self, telegram_user_id: int, event_id: UUID
    ) -> tuple[str, InlineKeyboardMarkup]:
        user, details = await self.today(telegram_user_id, current_window=False)
        for item in details:
            if item.event.id == event_id and item.event.status is not IntakeEventStatus.CANCELLED:
                if user.timezone is None:
                    raise TimezoneRequiredError
                return format_intake_detail(item, user.timezone)
        raise IntakeEventNotFoundError

    async def apply_action(self, telegram_user_id: int, callback: EventCallback) -> None:
        if callback.action is EventAction.VIEW:
            raise ValueError("Viewing an intake does not change its status")
        user = await self._get_or_create_user(telegram_user_id)
        target = {
            EventAction.TAKE: IntakeEventStatus.TAKEN,
            EventAction.SNOOZE: IntakeEventStatus.SNOOZED,
            EventAction.SKIP: IntakeEventStatus.SKIPPED,
            EventAction.UNDO: IntakeEventStatus.SCHEDULED,
        }[callback.action]
        snoozed_until = (
            self._clock() + timedelta(minutes=15) if callback.action is EventAction.SNOOZE else None
        )
        await self._transition_event(
            user.id,
            callback.event_id,
            target,
            source=EventSource.USER,
            snoozed_until=snoozed_until,
        )

    async def snooze(self, telegram_user_id: int, event_id: UUID, minutes: int) -> None:
        if minutes not in {15, 30, 60}:
            raise ValueError("Invalid snooze request")
        user = await self._get_or_create_user(telegram_user_id)
        await self._transition_event(
            user.id,
            event_id,
            IntakeEventStatus.SNOOZED,
            source=EventSource.USER,
            snoozed_until=self._clock() + timedelta(minutes=minutes),
        )
