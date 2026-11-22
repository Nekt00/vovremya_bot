from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from pydantic import ValidationError
from pytest import MonkeyPatch

from medication_reminder.shared.config import Settings
from medication_reminder.telegram.statistics import create_statistics_router, stats_keyboard


@pytest.mark.asyncio
@pytest.mark.parametrize("is_callback", [False, True])
@pytest.mark.parametrize("authorized", [False, True])
async def test_statistics_authorization(authorized: bool, is_callback: bool) -> None:
    bot = Bot(token="123:ABC")
    dispatcher = Dispatcher()
    dispatcher.include_router(create_statistics_router((42,)))
    dispatcher["database_session"] = AsyncMock()
    sender = User(id=42 if authorized else 99, is_bot=False, first_name="User")
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=sender.id, type="private"),
        from_user=sender,
        text="/stats",
    )
    update = (
        Update(
            update_id=1,
            callback_query=CallbackQuery(
                id="test", from_user=sender, chat_instance="test", message=message, data="stats:7"
            ),
        )
        if is_callback
        else Update(update_id=1, message=message)
    )
    with (
        patch(
            "medication_reminder.telegram.statistics.statistics",
            new_callable=AsyncMock,
            return_value="Statistics",
        ) as query,
        patch.object(bot.session, "make_request", new_callable=AsyncMock),
    ):
        await dispatcher.feed_update(bot, update)
    assert query.await_count == int(authorized)
    if authorized:
        assert query.await_args is not None
        assert query.await_args.args[1] == (7 if is_callback else 1)


def test_admin_access_is_opt_in_and_ids_must_be_positive(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEDICATION_TELEGRAM_ADMIN_IDS", raising=False)
    assert Settings().telegram_admin_ids == ()
    with pytest.raises(ValidationError):
        Settings(telegram_admin_ids=(0,))
    assert [button.callback_data for button in stats_keyboard(7).inline_keyboard[0]] == [
        "stats:1",
        "stats:7",
        "stats:30",
    ]
