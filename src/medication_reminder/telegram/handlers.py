import json

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from medication_reminder.families.service import FamilyService
from medication_reminder.intake_events.application.use_cases import (
    IntakeEventNotFoundError,
    IntakeEventUpdateConflictError,
)
from medication_reminder.intake_events.domain.event import InvalidIntakeTransitionError
from medication_reminder.shared.timezones import InvalidTimezoneError
from medication_reminder.telegram.callbacks import (
    EventAction,
    EventCallback,
    SetTakeAllCallback,
    SnoozeCallback,
)
from medication_reminder.telegram.clean_chat import (
    clear_recent_messages,
    delete_family_reminder_messages,
)
from medication_reminder.telegram.formatting import (
    format_history,
    format_intake_editor,
    snooze_keyboard,
)
from medication_reminder.telegram.keyboards import (
    HISTORY_BUTTON,
    SETTINGS_BUTTON,
    TODAY_BUTTON,
    settings_keyboard,
    timezone_keyboard,
)
from medication_reminder.telegram.regimen_handlers import create_regimen_management_router
from medication_reminder.telegram.screen import answer_main_screen
from medication_reminder.telegram.service import (
    TelegramApplicationService,
    TimezoneRequiredError,
)
from medication_reminder.telegram.today import show_today_from_callback
from medication_reminder.telegram.transactions import CommitDatabase
from medication_reminder.telegram.ui import DANGER_STYLE, DELETE, SETTINGS


class TimezoneSetup(StatesGroup):
    waiting_for_iana = State()


def _is_private_message(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE


def _is_private_callback(callback: CallbackQuery) -> bool:
    return isinstance(callback.message, Message) and _is_private_message(callback.message)


def create_clean_chat_router(*, mini_app_url: str | None) -> Router:
    router = Router(name="clean_chat")

    @router.message(Command("clear"))
    async def clear_chat(
        message: Message,
        state: FSMContext,
        bot: Bot,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await state.clear()
        await clear_recent_messages(
            bot,
            chat_id=message.chat.id,
            latest_message_id=message.message_id,
        )
        await show_today_dashboard(
            message,
            _required_telegram_id(message),
            state,
            telegram_service,
            mini_app_url=mini_app_url,
            restore_main_menu=True,
        )

    return router


def create_router(*, mini_app_url: str | None) -> Router:
    router = Router(name="telegram")

    @router.message(CommandStart())
    async def start(
        message: Message,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        telegram_id = _telegram_id(message)
        if telegram_id is None:
            return
        await state.clear()
        user = await telegram_service.ensure_user(telegram_id)
        if user.timezone is None:
            await request_timezone_setup(message, state, mini_app_url, welcome=True)
            return
        await show_today_dashboard(
            message,
            telegram_id,
            state,
            telegram_service,
            mini_app_url=mini_app_url,
            restore_main_menu=True,
            welcome_back=True,
        )

    @router.message(Command("mydata"))
    async def export_my_data(
        message: Message,
        telegram_service: TelegramApplicationService,
    ) -> None:
        telegram_id = _required_telegram_id(message)
        payload = await telegram_service.export_user_data(telegram_id)
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        await message.answer_document(
            BufferedInputFile(content, filename="vovremya-med-data.json"),
            caption="Ваши данные из бота.",
        )

    @router.message(Command("delete_me"))
    async def delete_my_data_confirmation(message: Message) -> None:
        await message.answer(
            "Удалить все курсы, историю и настройки? Это действие нельзя отменить.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{DELETE} Удалить все данные",
                            callback_data="privacy:delete:confirm",
                            style=DANGER_STYLE,
                        )
                    ],
                    [InlineKeyboardButton(text="Отмена", callback_data="privacy:delete:cancel")],
                ]
            ),
        )

    @router.callback_query(F.data == "privacy:delete:cancel")
    async def cancel_delete_my_data(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await show_today_from_callback(callback, state, telegram_service)
        await callback.answer()

    @router.callback_query(F.data == "privacy:delete:confirm")
    async def delete_my_data(
        callback: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        family_service: FamilyService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        removed = await family_service.remove_owned_assignments_for_account_deletion(
            callback.from_user.id
        )
        deleted = await telegram_service.delete_user_data(callback.from_user.id)
        await commit_database()
        await delete_family_reminder_messages(bot, removed.chats)
        await state.clear()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Все ваши данные удалены. Отправьте /start, если захотите начать заново."
            )
        await callback.answer("Данные удалены" if deleted else "Данных уже нет")

    @router.message(Command("timezone"))
    async def timezone_command(message: Message, state: FSMContext) -> None:
        await request_timezone_setup(message, state, mini_app_url)

    @router.message(Command("settings"))
    @router.message(F.text == SETTINGS_BUTTON)
    async def settings_menu(
        message: Message,
        telegram_service: TelegramApplicationService,
    ) -> None:
        user = await telegram_service.ensure_user(_required_telegram_id(message))
        await answer_main_screen(
            message,
            _settings_text(user.timezone, user.reminder_repeat_minutes, user.reminders_enabled),
            settings_keyboard(
                repeat_minutes=user.reminder_repeat_minutes,
                enabled=user.reminders_enabled,
            ),
        )

    @router.callback_query(F.data == "nav:settings")
    async def settings_callback(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await state.clear()
        user = await telegram_service.ensure_user(callback.from_user.id)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                _settings_text(user.timezone, user.reminder_repeat_minutes, user.reminders_enabled),
                reply_markup=settings_keyboard(
                    repeat_minutes=user.reminder_repeat_minutes, enabled=user.reminders_enabled
                ),
            )
        await callback.answer()

    @router.callback_query(F.data == "settings:tz")
    async def settings_timezone(callback: CallbackQuery, state: FSMContext) -> None:
        if isinstance(callback.message, Message):
            await request_timezone_setup(callback.message, state, mini_app_url)
        await callback.answer()

    @router.callback_query(F.data == "nav:today")
    async def return_to_today(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await state.clear()
        if isinstance(callback.message, Message):
            await show_today_dashboard(
                callback.message,
                callback.from_user.id,
                state,
                telegram_service,
                mini_app_url=mini_app_url,
                restore_main_menu=True,
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("settings:repeat:"))
    async def settings_repeat(
        callback: CallbackQuery,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        try:
            minutes = int((callback.data or "").rsplit(":", 1)[-1])
            user = await telegram_service.update_reminder_preferences(
                callback.from_user.id,
                repeat_minutes=minutes,
            )
            await commit_database()
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    _settings_text(user.timezone, minutes, user.reminders_enabled),
                    reply_markup=settings_keyboard(
                        repeat_minutes=minutes,
                        enabled=user.reminders_enabled,
                    ),
                )
            await callback.answer("Интервал сохранён")
        except ValueError:
            await callback.answer("Некорректный интервал", show_alert=True)

    @router.callback_query(F.data.startswith("settings:enabled:"))
    async def settings_enabled(
        callback: CallbackQuery,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        enabled = (callback.data or "").endswith(":1")
        user = await telegram_service.update_reminder_preferences(
            callback.from_user.id,
            enabled=enabled,
        )
        await commit_database()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                _settings_text(user.timezone, user.reminder_repeat_minutes, enabled),
                reply_markup=settings_keyboard(
                    repeat_minutes=user.reminder_repeat_minutes,
                    enabled=enabled,
                ),
            )
        await callback.answer("Напоминания включены" if enabled else "Напоминания выключены")

    @router.callback_query(F.data.startswith("tz:"))
    async def timezone_preset(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        response = "Не удалось сохранить часовой пояс."
        try:
            telegram_id = callback.from_user.id
            timezone = callback.data.removeprefix("tz:") if callback.data else ""
            await telegram_service.update_timezone(telegram_id, timezone)
            await commit_database()
            await state.clear()
            if isinstance(callback.message, Message):
                await show_today_dashboard(
                    callback.message,
                    telegram_id,
                    state,
                    telegram_service,
                    mini_app_url=mini_app_url,
                    restore_main_menu=True,
                )
            response = "Часовой пояс сохранён"
        except InvalidTimezoneError:
            response = "Этот часовой пояс не поддерживается"
        finally:
            await callback.answer(response)

    @router.message(TimezoneSetup.waiting_for_iana)
    async def timezone_manual(
        message: Message,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        telegram_id = _telegram_id(message)
        if telegram_id is None:
            return
        value = message.text or ""
        try:
            await telegram_service.update_timezone(telegram_id, value)
        except InvalidTimezoneError:
            existing = await telegram_service.ensure_user(telegram_id)
            if existing.timezone is not None:
                await state.clear()
                await show_today_dashboard(
                    message,
                    telegram_id,
                    state,
                    telegram_service,
                    mini_app_url=mini_app_url,
                    restore_main_menu=True,
                )
                return
            await message.answer(
                "Не удалось распознать часовой пояс. Отправьте его в формате "
                "<code>Europe/Moscow</code>.",
                reply_markup=timezone_keyboard(mini_app_url),
            )
            return
        await commit_database()
        await state.clear()
        await show_today_dashboard(
            message,
            telegram_id,
            state,
            telegram_service,
            mini_app_url=mini_app_url,
            restore_main_menu=True,
        )

    @router.message(Command("today"))
    @router.message(F.text == TODAY_BUTTON)
    async def today(
        message: Message,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        telegram_id = _telegram_id(message)
        if telegram_id is None:
            return
        await show_today_dashboard(
            message,
            telegram_id,
            state,
            telegram_service,
            mini_app_url=mini_app_url,
        )

    @router.message(Command("history"))
    @router.message(F.text == HISTORY_BUTTON)
    async def history(
        message: Message,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        telegram_id = _telegram_id(message)
        if telegram_id is None:
            return
        try:
            user, details = await telegram_service.history(telegram_id, days=7)
        except TimezoneRequiredError:
            await request_timezone_setup(message, state, mini_app_url)
            return
        text, markup = format_history(
            details,
            _required_timezone(user.timezone),
            days=7,
        )
        await answer_main_screen(message, text, markup)

    @router.callback_query(F.data.startswith("history:"))
    async def history_period(
        callback: CallbackQuery,
        telegram_service: TelegramApplicationService,
    ) -> None:
        try:
            days = int((callback.data or "").removeprefix("history:"))
            user, details = await telegram_service.history(callback.from_user.id, days=days)
            text, markup = format_history(
                details,
                _required_timezone(user.timezone),
                days=days,
            )
            if isinstance(callback.message, Message):
                await callback.message.edit_text(text, reply_markup=markup)
            await callback.answer()
        except (ValueError, TimezoneRequiredError):
            await callback.answer("Не удалось открыть историю", show_alert=True)

    @router.callback_query(F.data == "intakes:edit")
    async def edit_intakes(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await state.clear()
        try:
            user, details = await telegram_service.today(
                callback.from_user.id, current_window=False
            )
            text, markup = format_intake_editor(details, _required_timezone(user.timezone))
            if isinstance(callback.message, Message):
                await callback.message.edit_text(text, reply_markup=markup)
        except TimezoneRequiredError:
            await callback.answer("Сначала настройте часовой пояс", show_alert=True)
            return
        await callback.answer()

    @router.callback_query(F.data.startswith("edit:ie:"))
    @router.callback_query(F.data.startswith(f"{EventCallback.PREFIX}:"))
    async def event_action(
        callback: CallbackQuery,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        response = "Не удалось выполнить действие"
        try:
            encoded = callback.data or ""
            editing = encoded.startswith("edit:")
            parsed = EventCallback.decode(encoded.removeprefix("edit:"))
            if editing and parsed.action not in {EventAction.TAKE, EventAction.UNDO}:
                raise ValueError("Invalid intake editor action")
            # Previously sent set reminders used TAKE for medication selection too.
            selecting_from_old_reminder = (
                not editing
                and parsed.action is EventAction.TAKE
                and isinstance(callback.message, Message)
                and callback.message.reply_markup is not None
                and any(
                    (button.callback_data or "").startswith(f"{SetTakeAllCallback.PREFIX}:")
                    for row in callback.message.reply_markup.inline_keyboard
                    for button in row
                )
            )
            if parsed.action is EventAction.VIEW or selecting_from_old_reminder:
                text, detail_markup = await telegram_service.intake_screen(
                    callback.from_user.id, parsed.event_id
                )
                if isinstance(callback.message, Message):
                    await callback.message.edit_text(text, reply_markup=detail_markup)
                response = "Выберите действие"
                return
            if parsed.action is EventAction.SNOOZE:
                if isinstance(callback.message, Message):
                    await callback.message.edit_reply_markup(
                        reply_markup=snooze_keyboard(parsed.event_id)
                    )
                response = "На сколько отложить?"
                return
            await telegram_service.apply_action(callback.from_user.id, parsed)
            await commit_database()
            markup: InlineKeyboardMarkup | None
            if editing:
                user, details = await telegram_service.today(
                    callback.from_user.id, current_window=False
                )
                text, markup = format_intake_editor(details, _required_timezone(user.timezone))
            else:
                text, markup = await telegram_service.today_screen(callback.from_user.id)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(text, reply_markup=markup)
            response = "Готово"
        except IntakeEventNotFoundError:
            response = "Приём не найден"
        except (IntakeEventUpdateConflictError, InvalidIntakeTransitionError):
            response = "Состояние уже изменилось — откройте «Сегодня» заново"
        except TimezoneRequiredError:
            response = "Сначала настройте часовой пояс командой /timezone"
        except ValueError:
            response = "Некорректная или устаревшая кнопка"
        finally:
            await callback.answer(response)

    @router.callback_query(F.data.startswith(f"{SnoozeCallback.PREFIX}:"))
    async def snooze_action(
        callback: CallbackQuery,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        response = "Не удалось отложить напоминание"
        try:
            parsed = SnoozeCallback.decode(callback.data or "")
            await telegram_service.snooze(
                callback.from_user.id,
                parsed.event_id,
                parsed.minutes,
            )
            await commit_database()
            text, markup = await telegram_service.today_screen(callback.from_user.id)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(text, reply_markup=markup)
            response = f"Отложено на {parsed.minutes} мин"
        except IntakeEventNotFoundError:
            response = "Приём не найден"
        except (IntakeEventUpdateConflictError, InvalidIntakeTransitionError):
            response = "Состояние уже изменилось — откройте «Сегодня» заново"
        except TimezoneRequiredError:
            response = "Сначала настройте часовой пояс командой /timezone"
        except ValueError:
            response = "Некорректная или устаревшая кнопка"
        finally:
            await callback.answer(response)

    router.include_router(create_regimen_management_router())
    return router


async def request_timezone_setup(
    message: Message,
    state: FSMContext,
    mini_app_url: str | None,
    *,
    welcome: bool = False,
) -> None:
    await state.set_state(TimezoneSetup.waiting_for_iana)
    introduction = (
        "👋 <b>Добро пожаловать во «Вовремя»</b>\n\n"
        "Я помогу соблюдать график таблеток, капсул и уколов: напомню о приёме, "
        "сохраню фактическое время и покажу историю.\n\n"
        if welcome
        else f"{SETTINGS} <b>Часовой пояс</b>\n\n"
    )
    await message.answer(
        introduction + "Для точных уведомлений выберите часовой пояс. Быстрее всего — определить "
        "его автоматически в приложении. Если нужного города нет в списке, отправьте "
        "часовой пояс в формате <code>Europe/Moscow</code>.",
        reply_markup=timezone_keyboard(mini_app_url),
    )


async def show_today_dashboard(
    message: Message,
    telegram_id: int,
    state: FSMContext,
    telegram_service: TelegramApplicationService,
    *,
    mini_app_url: str | None,
    restore_main_menu: bool = False,
    welcome_back: bool = False,
) -> None:
    """Show the current intake window with its inline actions."""
    try:
        text, markup = await telegram_service.today_screen(telegram_id)
    except TimezoneRequiredError:
        await request_timezone_setup(message, state, mini_app_url)
        return
    if welcome_back:
        text = f"👋 <b>С возвращением!</b>\n\n{text}"
    if restore_main_menu:
        await answer_main_screen(message, text, markup, restore_menu=True)
        return
    await message.answer(text, reply_markup=markup)


def _telegram_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user is not None else None


def _required_telegram_id(message: Message) -> int:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        raise ValueError("Telegram user is required")
    return telegram_id


def _required_timezone(value: str | None) -> str:
    if value is None:
        raise TimezoneRequiredError
    return value


def _settings_text(timezone: str | None, repeat_minutes: int, enabled: bool) -> str:
    status = "включены" if enabled else "выключены"
    timezone_text = timezone or "не настроен"
    return (
        f"{SETTINGS} <b>Настройки напоминаний</b>\n\n"
        f"🌍 Часовой пояс: <code>{timezone_text}</code>\n"
        f"🔔 Напоминания: <b>{status}</b>\n"
        f"⏱ Повтор: каждые <b>{repeat_minutes} мин</b>, пока приём не отмечен\n\n"
        "Выберите, что хотите изменить."
    )
