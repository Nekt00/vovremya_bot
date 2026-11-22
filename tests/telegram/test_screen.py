from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from medication_reminder.telegram.screen import answer_main_screen


@pytest.mark.asyncio
async def test_main_screen_sends_inline_actions_without_editing_a_reply_keyboard_message() -> None:
    screen = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(answer=AsyncMock(return_value=screen))
    inline = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отметить приём вручную", callback_data="intakes:edit")]
        ]
    )

    await answer_main_screen(message, "Экран", inline)  # type: ignore[arg-type]

    assert message.answer.await_count == 1
    content = message.answer.await_args
    assert content.args == ("Экран",)
    assert content.kwargs["reply_markup"] == inline
    screen.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_screen_restores_reply_menu_only_when_requested() -> None:
    message = SimpleNamespace(answer=AsyncMock())

    await answer_main_screen(message, "Экран", restore_menu=True)  # type: ignore[arg-type]

    assert message.answer.await_count == 2
    menu, content = message.answer.await_args_list
    assert isinstance(menu.kwargs["reply_markup"], ReplyKeyboardMarkup)
    assert menu.kwargs["reply_markup"].is_persistent is True
    assert content.args == ("Экран",)
