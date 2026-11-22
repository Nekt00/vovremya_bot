from aiogram.types import InlineKeyboardMarkup, Message

from medication_reminder.telegram.keyboards import main_menu


async def answer_main_screen(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    restore_menu: bool = False,
) -> None:
    """Keep the reply-menu anchor separate from the editable inline screen."""
    if restore_menu:
        await message.answer(
            "<b>Вовремя</b>\nРазделы доступны в меню у строки ввода.",
            reply_markup=main_menu(),
            disable_notification=True,
        )
    await message.answer(text, reply_markup=reply_markup)
