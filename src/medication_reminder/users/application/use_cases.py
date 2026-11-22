from medication_reminder.users.application.repositories import (
    ReminderPreferencesRepository,
    UserRepository,
)
from medication_reminder.users.domain.user import User
from medication_reminder.users.domain.validation import (
    validate_telegram_user_id,
    validate_timezone,
)


class UserNotFoundError(LookupError):
    pass


class GetOrCreateUser:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def __call__(self, telegram_user_id: int) -> User:
        validate_telegram_user_id(telegram_user_id)
        return await self._repository.get_or_create(telegram_user_id)


class UpdateUserTimezone:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def __call__(self, telegram_user_id: int, timezone: str) -> User:
        validate_telegram_user_id(telegram_user_id)
        validated_timezone = validate_timezone(timezone)
        user = await self._repository.update_timezone(telegram_user_id, validated_timezone)
        if user is None:
            raise UserNotFoundError(f"User with Telegram ID {telegram_user_id} was not found")
        return user


class UpdateReminderPreferences:
    def __init__(self, repository: ReminderPreferencesRepository) -> None:
        self._repository = repository

    async def __call__(
        self,
        telegram_user_id: int,
        *,
        repeat_minutes: int,
        enabled: bool,
    ) -> User:
        validate_telegram_user_id(telegram_user_id)
        if repeat_minutes not in {15, 30, 60}:
            raise ValueError("Reminder repeat interval must be 15, 30, or 60 minutes")
        user = await self._repository.update_reminder_preferences(
            telegram_user_id,
            repeat_minutes=repeat_minutes,
            enabled=enabled,
        )
        if user is None:
            raise UserNotFoundError(f"User with Telegram ID {telegram_user_id} was not found")
        return user
