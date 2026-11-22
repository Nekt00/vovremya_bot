from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.methods import DeleteMessage, SendMessage
from aiogram.methods.base import TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)
from redis.asyncio import Redis

from medication_reminder.families.service import FamilyChatCleanup
from medication_reminder.telegram.clean_chat import (
    SingleScreenRequestMiddleware,
    clear_recent_messages,
    delete_family_reminder_messages,
)
from medication_reminder.telegram.handlers import _is_private_callback, _is_private_message
from medication_reminder.telegram.keyboards import main_menu


class FakeLock(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeRedis:
    def __init__(self, value: str | None = None) -> None:
        self.value = value

    def lock(self, *args: object, **kwargs: object) -> FakeLock:
        return FakeLock()

    async def get(self, key: str) -> str | None:
        return self.value

    async def set(self, key: str, value: str, **kwargs: object) -> None:
        self.value = value


class FakeBot:
    def __init__(self) -> None:
        self.deleted_batches: list[list[int]] = []

    async def delete_messages(self, *, chat_id: int, message_ids: list[int]) -> bool:
        assert chat_id == 42
        self.deleted_batches.append(message_ids)
        return True


def test_sensitive_handlers_reject_shared_chats() -> None:
    sender = User(id=42, is_bot=False, first_name="Test")
    private_message = Message(
        message_id=1,
        date=datetime(2026, 10, 19, tzinfo=UTC),
        chat=Chat(id=42, type="private"),
        from_user=sender,
        text="/today",
    )
    group_message = private_message.model_copy(update={"chat": Chat(id=-1001, type="supergroup")})

    assert _is_private_message(private_message) is True
    assert _is_private_message(group_message) is False
    assert (
        _is_private_callback(
            CallbackQuery(
                id="callback",
                from_user=sender,
                chat_instance="instance",
                message=group_message,
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_single_screen_sends_new_message_before_deleting_previous() -> None:
    middleware = SingleScreenRequestMiddleware(cast(Redis, FakeRedis("11")))
    bot = Bot(token="123:ABC")
    calls: list[TelegramMethod[Any]] = []

    async def make_request(bot: Bot, method: TelegramMethod[Any]) -> Any:
        calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=12,
                date=datetime(2026, 10, 19, tzinfo=UTC),
                chat=Chat(id=42, type="private"),
                text=method.text,
            )
        return True

    result = await middleware(make_request, bot, SendMessage(chat_id=42, text="Экран"))

    assert isinstance(result, Message)
    assert [type(method) for method in calls] == [SendMessage, DeleteMessage]
    assert cast(DeleteMessage, calls[1]).message_id == 11


@pytest.mark.asyncio
async def test_reply_menu_is_installed_after_deleting_old_keyboard_message() -> None:
    middleware = SingleScreenRequestMiddleware(cast(Redis, FakeRedis("11")))
    bot = Bot(token="123:ABC")
    calls: list[TelegramMethod[Any]] = []

    async def transport(bot: Bot, method: TelegramMethod[Any]) -> Any:
        calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=12,
                date=datetime.now(UTC),
                chat=Chat(id=42, type="private"),
                text=method.text,
            )
        return True

    await middleware(
        transport, bot, SendMessage(chat_id=42, text="Вовремя", reply_markup=main_menu())
    )

    assert [type(method) for method in calls] == [DeleteMessage, SendMessage]
    assert cast(DeleteMessage, calls[0]).message_id == 11
    keyboard = cast(SendMessage, calls[-1]).reply_markup
    assert keyboard == main_menu()
    assert main_menu().one_time_keyboard is False


@pytest.mark.asyncio
async def test_replacing_content_preserves_the_reply_menu_anchor() -> None:
    class StoredRedis(FakeRedis):
        async def get(self, key: str) -> str | None:
            return "9" if key.endswith(":menu-message") else "11"

    middleware = SingleScreenRequestMiddleware(cast(Redis, StoredRedis()))
    bot = Bot(token="123:ABC")
    deleted: set[int] = set()

    async def make_request(bot: Bot, method: TelegramMethod[Any]) -> Any:
        if isinstance(method, SendMessage):
            return Message(
                message_id=12,
                date=datetime(2026, 10, 27, tzinfo=UTC),
                chat=Chat(id=42, type="private"),
                text=method.text,
            )
        if isinstance(method, DeleteMessage):
            deleted.add(method.message_id)
        return True

    await middleware(make_request, bot, SendMessage(chat_id=42, text="Сегодня"))
    assert deleted == {11}


@pytest.mark.asyncio
async def test_repeated_screens_and_reminders_keep_one_menu_and_one_inline_message() -> None:
    class StoredRedis(FakeRedis):
        def __init__(self) -> None:
            self.values: dict[str, str] = {}

        async def get(self, key: str) -> str | None:
            return self.values.get(key)

        async def set(self, key: str, value: str, **kwargs: object) -> None:
            self.values[key] = value

    redis = StoredRedis()
    middleware = SingleScreenRequestMiddleware(cast(Redis, redis))
    bot = Bot(token="123:ABC")
    live: dict[int, SendMessage] = {}
    next_id = 10

    async def transport(bot: Bot, method: TelegramMethod[Any]) -> Any:
        nonlocal next_id
        if isinstance(method, SendMessage):
            next_id += 1
            live[next_id] = method
            return Message(
                message_id=next_id,
                date=datetime.now(UTC),
                chat=Chat(id=42, type="private"),
                text=method.text,
            )
        if isinstance(method, DeleteMessage):
            live.pop(method.message_id)
        return True

    inline = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отметить приём вручную", callback_data="intakes:edit")]
        ]
    )
    for text in ("Сегодня", "Курсы"):
        await middleware(
            transport, bot, SendMessage(chat_id=42, text="Вовремя", reply_markup=main_menu())
        )
        await middleware(transport, bot, SendMessage(chat_id=42, text=text, reply_markup=inline))
    await middleware(
        transport, bot, SendMessage(chat_id=42, text="Напоминание", reply_markup=inline)
    )
    assert set(live) == {13, 15}
    assert live[13].reply_markup == main_menu()
    assert live[15].reply_markup == inline
    assert redis.values["medication-ui:123:42:menu-message"] == "13"
    assert redis.values["medication-ui:123:42:last-message"] == "15"


@pytest.mark.asyncio
async def test_clear_recent_messages_uses_telegram_batch_limit() -> None:
    bot = FakeBot()

    await clear_recent_messages(
        cast(Bot, bot),
        chat_id=42,
        latest_message_id=250,
        limit=250,
    )

    assert [len(batch) for batch in bot.deleted_batches] == [100, 100, 50]
    assert bot.deleted_batches[0][0] == 1
    assert bot.deleted_batches[-1][-1] == 250


@pytest.mark.asyncio
async def test_mini_app_refresh_edits_existing_screen_without_sending_a_reminder() -> None:
    bot = Bot(token="123:ABC")
    middleware = SingleScreenRequestMiddleware(cast(Redis, FakeRedis("11")))
    with patch.object(bot, "edit_message_text", new_callable=AsyncMock) as edit:
        await middleware.refresh_current_screen(
            bot, chat_id=42, text="Сегодня: принято", reply_markup=None
        )

    edit.assert_awaited_once_with(
        chat_id=42, message_id=11, text="Сегодня: принято", reply_markup=None, parse_mode="HTML"
    )


@pytest.mark.asyncio
async def test_mini_app_refresh_does_not_create_a_chat_without_a_saved_screen() -> None:
    bot = Bot(token="123:ABC")
    middleware = SingleScreenRequestMiddleware(cast(Redis, FakeRedis()))
    with patch.object(bot, "edit_message_text", new_callable=AsyncMock) as edit:
        await middleware.refresh_current_screen(bot, chat_id=42, text="Сегодня", reply_markup=None)

    edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_family_reminders_uses_saved_message_ids() -> None:
    bot = FakeBot()

    await delete_family_reminder_messages(
        cast(Bot, bot),
        (FamilyChatCleanup(telegram_user_id=42, message_ids=tuple(range(1, 206))),),
    )

    assert [len(batch) for batch in bot.deleted_batches] == [100, 100, 5]
    assert bot.deleted_batches[-1] == [201, 202, 203, 204, 205]
