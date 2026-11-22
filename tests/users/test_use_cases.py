from datetime import UTC, datetime
from uuid import uuid4

import pytest

from medication_reminder.users.application.repositories import (
    ReminderPreferencesRepository,
    UserRepository,
)
from medication_reminder.users.application.use_cases import (
    GetOrCreateUser,
    UpdateReminderPreferences,
    UpdateUserTimezone,
    UserNotFoundError,
)
from medication_reminder.users.domain.user import User
from medication_reminder.users.domain.validation import (
    InvalidTelegramUserIdError,
    InvalidTimezoneError,
)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    async def get_or_create(self, telegram_user_id: int) -> User:
        existing = self.users.get(telegram_user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        user = User(uuid4(), telegram_user_id, None, now, now)
        self.users[telegram_user_id] = user
        return user

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        return self.users.get(telegram_user_id)

    async def update_timezone(self, telegram_user_id: int, timezone: str) -> User | None:
        existing = self.users.get(telegram_user_id)
        if existing is None:
            return None
        updated = User(
            existing.id,
            existing.telegram_user_id,
            timezone,
            existing.created_at,
            datetime.now(UTC),
        )
        self.users[telegram_user_id] = updated
        return updated

    async def update_reminder_preferences(
        self,
        telegram_user_id: int,
        *,
        repeat_minutes: int | None = None,
        enabled: bool | None = None,
    ) -> User | None:
        existing = self.users.get(telegram_user_id)
        if existing is None:
            return None
        updated = User(
            existing.id,
            existing.telegram_user_id,
            existing.timezone,
            existing.created_at,
            datetime.now(UTC),
            repeat_minutes or existing.reminder_repeat_minutes,
            existing.reminders_enabled if enabled is None else enabled,
        )
        self.users[telegram_user_id] = updated
        return updated


def assert_user_repository(repository: UserRepository) -> None:
    assert repository is not None


def assert_preferences_repository(repository: ReminderPreferencesRepository) -> None:
    assert repository is not None


@pytest.mark.asyncio
async def test_get_or_create_returns_same_user_for_same_telegram_id() -> None:
    repository = InMemoryUserRepository()
    assert_user_repository(repository)
    use_case = GetOrCreateUser(repository)

    first = await use_case(123456789)
    second = await use_case(123456789)

    assert first == second
    assert first.timezone is None
    assert first.created_at.tzinfo is UTC


@pytest.mark.asyncio
async def test_get_or_create_rejects_invalid_telegram_id() -> None:
    use_case = GetOrCreateUser(InMemoryUserRepository())

    with pytest.raises(InvalidTelegramUserIdError):
        await use_case(0)


@pytest.mark.asyncio
async def test_update_timezone_accepts_iana_identifier() -> None:
    repository = InMemoryUserRepository()
    await GetOrCreateUser(repository)(123456789)

    updated = await UpdateUserTimezone(repository)(123456789, "Europe/Moscow")

    assert updated.timezone == "Europe/Moscow"


@pytest.mark.asyncio
async def test_update_timezone_rejects_unknown_identifier() -> None:
    repository = InMemoryUserRepository()
    await GetOrCreateUser(repository)(123456789)

    with pytest.raises(InvalidTimezoneError):
        await UpdateUserTimezone(repository)(123456789, "UTC+03:00")


@pytest.mark.asyncio
async def test_update_timezone_requires_existing_user() -> None:
    with pytest.raises(UserNotFoundError):
        await UpdateUserTimezone(InMemoryUserRepository())(123456789, "Europe/Moscow")


@pytest.mark.asyncio
async def test_update_reminder_preferences_changes_interval_and_state() -> None:
    repository = InMemoryUserRepository()
    assert_preferences_repository(repository)
    await GetOrCreateUser(repository)(123456789)

    updated = await UpdateReminderPreferences(repository)(
        123456789,
        repeat_minutes=60,
        enabled=False,
    )

    assert updated.reminder_repeat_minutes == 60
    assert updated.reminders_enabled is False


@pytest.mark.asyncio
async def test_update_reminder_preferences_rejects_unknown_interval() -> None:
    repository = InMemoryUserRepository()
    await GetOrCreateUser(repository)(123456789)

    with pytest.raises(ValueError, match="15, 30, or 60"):
        await UpdateReminderPreferences(repository)(
            123456789,
            repeat_minutes=45,
            enabled=True,
        )
