from typing import Protocol

from medication_reminder.users.domain.user import User


class UserRepository(Protocol):
    async def get_or_create(self, telegram_user_id: int) -> User: ...

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None: ...

    async def update_timezone(self, telegram_user_id: int, timezone: str) -> User | None: ...


class ReminderPreferencesRepository(Protocol):
    async def update_reminder_preferences(
        self,
        telegram_user_id: int,
        *,
        repeat_minutes: int | None = None,
        enabled: bool | None = None,
    ) -> User | None: ...


class UserDataRepository(Protocol):
    async def export_user_data(self, telegram_user_id: int) -> dict[str, object] | None: ...

    async def delete_user_data(self, telegram_user_id: int) -> bool: ...
