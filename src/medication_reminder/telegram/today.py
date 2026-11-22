from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from medication_reminder.telegram.screen import answer_main_screen
from medication_reminder.telegram.service import (
    TelegramApplicationService,
    TimezoneRequiredError,
)


async def show_today_from_message(
    message: Message,
    state: FSMContext,
    telegram_service: TelegramApplicationService,
    *,
    restore_main_menu: bool = False,
) -> None:
    if message.from_user is None:
        return
    await state.clear()
    try:
        text, markup = await telegram_service.today_screen(message.from_user.id)
    except TimezoneRequiredError:
        await message.answer("Сначала настройте часовой пояс командой /timezone.")
        return
    await answer_main_screen(message, text, markup, restore_menu=restore_main_menu)


async def show_today_from_callback(
    callback: CallbackQuery,
    state: FSMContext,
    telegram_service: TelegramApplicationService,
    *,
    restore_main_menu: bool = False,
) -> None:
    await state.clear()
    if not isinstance(callback.message, Message):
        return
    try:
        text, markup = await telegram_service.today_screen(callback.from_user.id)
    except TimezoneRequiredError:
        await callback.message.edit_text("Сначала настройте часовой пояс командой /timezone.")
        return
    await answer_main_screen(
        callback.message,
        text,
        markup,
        restore_menu=restore_main_menu,
    )
