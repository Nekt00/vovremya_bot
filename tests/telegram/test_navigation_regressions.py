from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage, EditMessageText, SendMessage
from aiogram.methods.base import TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    Update,
    User,
)

from medication_reminder.regimens.domain.regimen import MedicationForm, RegimenStatus
from medication_reminder.telegram.callbacks import EventAction, EventCallback
from medication_reminder.telegram.clean_chat import DeleteIncomingMessageMiddleware
from medication_reminder.telegram.formatting import format_history, format_today
from medication_reminder.telegram.handlers import create_router
from medication_reminder.telegram.keyboards import REGIMENS_BUTTON
from medication_reminder.telegram.medication_set_views import sets_keyboard
from medication_reminder.telegram.regimen_formatting import format_regimen_list
from medication_reminder.telegram.wizard import create_wizard_router


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_selecting_medication_opens_detail_without_taking_any_medication(
    legacy: bool,
) -> None:
    bot = Bot(token="123:ABC")
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(mini_app_url=None))
    event_id = uuid4()
    screen = ("Витамин D · выбранный препарат", InlineKeyboardMarkup(inline_keyboard=[]))
    service = SimpleNamespace(
        intake_screen=AsyncMock(return_value=screen),
        apply_action=AsyncMock(),
        today_screen=AsyncMock(),
    )
    commit = AsyncMock()
    dispatcher["telegram_service"] = service
    dispatcher["commit_database"] = commit
    callback = CallbackQuery(
        id="selected",
        chat_instance="instance",
        from_user=User(id=42, is_bot=False, first_name="Test"),
        message=Message(
            message_id=11,
            date=datetime.now(UTC),
            chat=Chat(id=42, type="private"),
            text="Утренний набор",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Принять всё", callback_data=f"sa:20261031:{uuid4()}"
                        )
                    ]
                ]
            ),
        ),
        data=EventCallback(event_id, EventAction.TAKE if legacy else EventAction.VIEW).encode(),
    )
    with patch.object(bot.session, "make_request", new_callable=AsyncMock) as transport:
        await dispatcher.feed_update(bot, Update(update_id=1, callback_query=callback))
    service.intake_screen.assert_awaited_once_with(42, event_id)
    service.apply_action.assert_not_awaited()
    service.today_screen.assert_not_awaited()
    commit.assert_not_awaited()
    edits = [
        call.args[1]
        for call in transport.await_args_list
        if isinstance(call.args[1], EditMessageText)
    ]
    assert len(edits) == 1
    assert edits[0].text == screen[0]
    assert edits[0].reply_markup == screen[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "restores_menu"),
    [("/start", True), ("/today", False), (REGIMENS_BUTTON, False)],
)
@pytest.mark.parametrize("failure_at", [None, "menu", "screen"])
async def test_real_routes_preserve_inline_buttons_and_always_delete_user_message(
    command: str, restores_menu: bool, failure_at: str | None
) -> None:
    bot = Bot(token="123:ABC")
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(DeleteIncomingMessageMiddleware())
    dispatcher.include_router(create_router(mini_app_url=None))
    dispatcher["telegram_service"] = SimpleNamespace(
        ensure_user=AsyncMock(return_value=SimpleNamespace(timezone="UTC")),
        today_screen=AsyncMock(return_value=format_today([], "UTC")),
    )
    dispatcher["regimen_service"] = SimpleNamespace(
        list_for_user=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=uuid4(),
                    medication_name="Тестовое назначение",
                    medication_form=MedicationForm.TABLET,
                    status=RegimenStatus.ACTIVE,
                )
            ]
        )
    )
    now = datetime.now(UTC)
    incoming = Message(
        message_id=10,
        date=now,
        chat=Chat(id=42, type="private"),
        from_user=User(id=42, is_bot=False, first_name="Test"),
        text=command,
    )
    calls: list[TelegramMethod[Any]] = []

    async def transport(bot: Bot, method: TelegramMethod[Any], **kwargs: Any) -> Any:
        calls.append(method)
        if isinstance(method, EditMessageText):
            raise TelegramBadRequest(method=method, message="message can't be edited")
        if isinstance(method, SendMessage):
            assert isinstance(method.reply_markup, (InlineKeyboardMarkup, ReplyKeyboardMarkup))
            stage = "menu" if isinstance(method.reply_markup, ReplyKeyboardMarkup) else "screen"
            if failure_at == stage:
                raise TelegramBadRequest(method=method, message="simulated sending failure")
            return Message(message_id=11, date=now, chat=incoming.chat, text=method.text)
        return True

    with patch.object(bot.session, "make_request", side_effect=transport):
        expected_failure = failure_at == "screen" or (failure_at == "menu" and restores_menu)
        if expected_failure:
            with pytest.raises(TelegramBadRequest, match="simulated sending failure"):
                await dispatcher.feed_update(bot, Update(update_id=1, message=incoming))
        else:
            await dispatcher.feed_update(bot, Update(update_id=1, message=incoming))
    assert [call.message_id for call in calls if isinstance(call, DeleteMessage)] == [10]
    assert not any(isinstance(call, EditMessageText) for call in calls)
    if not expected_failure:
        sent_messages = [call for call in calls if isinstance(call, SendMessage)]
        assert len(sent_messages) == (2 if restores_menu else 1)
        if restores_menu:
            assert isinstance(sent_messages[0].reply_markup, ReplyKeyboardMarkup)
        sent = sent_messages[-1]
        assert isinstance(sent.reply_markup, InlineKeyboardMarkup)
        buttons = [button for row in sent.reply_markup.inline_keyboard for button in row]
        if command == REGIMENS_BUTTON:
            assert any((button.callback_data or "").startswith("rg:v:") for button in buttons)
        else:
            assert any(button.callback_data == "intakes:edit" for button in buttons)
    await dispatcher.storage.close()
    await bot.session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["rg:list", "nav:settings", "nav:add"])
async def test_home_navigation_opens_sections_using_callback_user_identity(action: str) -> None:
    bot = Bot(token="123:ABC")
    dispatcher = Dispatcher()
    dispatcher.include_router(create_wizard_router(mini_app_url=None))
    dispatcher.include_router(create_router(mini_app_url=None))
    ensure_user = AsyncMock(
        return_value=SimpleNamespace(
            timezone="UTC", reminder_repeat_minutes=30, reminders_enabled=True
        )
    )
    require_timezone = AsyncMock()
    list_regimens = AsyncMock(return_value=[])
    dispatcher["telegram_service"] = SimpleNamespace(ensure_user=ensure_user)
    dispatcher["regimen_service"] = SimpleNamespace(list_for_user=list_regimens)
    dispatcher["wizard_service"] = SimpleNamespace(require_timezone=require_timezone)
    dispatcher["family_service"] = SimpleNamespace(
        list_targets=AsyncMock(return_value=[]),
        can_manage_personal_regimens=AsyncMock(return_value=True),
    )
    bot_message = Message(
        message_id=11,
        date=datetime.now(UTC),
        chat=Chat(id=42, type="private"),
        from_user=User(id=123, is_bot=True, first_name="Bot"),
        text="Сегодня",
    )
    callback = CallbackQuery(
        id="callback",
        chat_instance="instance",
        message=bot_message,
        from_user=User(id=42, is_bot=False, first_name="Test"),
        data=action,
    )

    async def transport(bot: Bot, method: TelegramMethod[Any], **kwargs: Any) -> Any:
        if isinstance(method, SendMessage):
            return Message(
                message_id=12, date=datetime.now(UTC), chat=bot_message.chat, text=method.text
            )
        return True

    with patch.object(bot.session, "make_request", side_effect=transport) as request:
        await dispatcher.feed_update(bot, Update(update_id=3, callback_query=callback))
    if action == "nav:add":
        require_timezone.assert_awaited_once_with(42)
        assert any(isinstance(call.args[1], SendMessage) for call in request.await_args_list)
    else:
        (ensure_user if action == "nav:settings" else list_regimens).assert_awaited_once_with(42)
        assert any(isinstance(call.args[1], EditMessageText) for call in request.await_args_list)
    await dispatcher.storage.close()
    await bot.session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type", ["private", "group"])
async def test_unhandled_message_is_cleaned_only_in_private_chat(chat_type: str) -> None:
    bot = Bot(token="123:ABC")
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(DeleteIncomingMessageMiddleware())
    message = Message(
        message_id=20,
        date=datetime.now(UTC),
        chat=Chat(id=42, type=chat_type),
        from_user=User(id=42, is_bot=False, first_name="Test"),
        text="неизвестное сообщение",
    )
    with patch.object(bot.session, "make_request", new_callable=AsyncMock) as transport:
        await dispatcher.feed_update(bot, Update(update_id=2, message=message))
    deletions = [call.args[1] for call in transport.await_args_list]
    if chat_type == "private":
        assert len(deletions) == 1
        assert isinstance(deletions[0], DeleteMessage)
        assert deletions[0].message_id == 20
    else:
        assert deletions == []
    await dispatcher.storage.close()
    await bot.session.close()


def test_main_sections_have_a_route_back_to_today() -> None:
    _, history = format_history([], "UTC", days=7)
    _, regimens = format_regimen_list([])
    for markup in (history, regimens, sets_keyboard([])):
        assert markup is not None
        assert any(
            button.callback_data == "nav:today" for row in markup.inline_keyboard for button in row
        )
