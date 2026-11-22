from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.analytics.service import statistics
from medication_reminder.telegram.clock import Clock, utc_now


def stats_keyboard(days: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"stats:{value}",
                    style="primary" if days == value else None,
                )
                for value, label in ((1, "Сегодня"), (7, "7 дней"), (30, "30 дней"))
            ],
            [InlineKeyboardButton(text="Сегодня · Мои приёмы", callback_data="nav:today")],
        ]
    )


def create_statistics_router(admin_ids: tuple[int, ...], *, clock: Clock = utc_now) -> Router:
    router = Router(name="statistics")
    router.message.filter(F.chat.type == "private")
    router.callback_query.filter(F.message.chat.type == "private")

    @router.message(Command("stats"))
    async def show_statistics(message: Message, database_session: AsyncSession) -> None:
        if message.from_user is None or message.from_user.id not in admin_ids:
            await message.answer("Этот раздел доступен только владельцу бота.")
            return
        await message.answer(
            await statistics(database_session, 1, clock()), reply_markup=stats_keyboard(1)
        )

    @router.callback_query(F.data.startswith("stats:"))
    async def change_period(callback: CallbackQuery, database_session: AsyncSession) -> None:
        if callback.from_user.id not in admin_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        try:
            days = int((callback.data or "").removeprefix("stats:"))
            if days not in (1, 7, 30):
                raise ValueError("Invalid period")
        except ValueError:
            await callback.answer("Неизвестный период", show_alert=True)
            return
        if isinstance(callback.message, Message):
            markup = stats_keyboard(days)
            if callback.message.reply_markup != markup:
                await callback.message.edit_text(
                    await statistics(database_session, days, clock()), reply_markup=markup
                )
        await callback.answer()

    return router
