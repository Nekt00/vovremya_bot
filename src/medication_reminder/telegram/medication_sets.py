from typing import cast
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from medication_reminder.medication_sets.application import MedicationSetError
from medication_reminder.medication_sets.presets import MEDICATION_SET_PRESETS
from medication_reminder.telegram.callbacks import SetTakeAllCallback
from medication_reminder.telegram.keyboards import SETS_BUTTON
from medication_reminder.telegram.medication_set_service import TelegramMedicationSetService
from medication_reminder.telegram.medication_set_views import (
    delete_confirmation_keyboard as _delete_confirmation_keyboard,
)
from medication_reminder.telegram.medication_set_views import (
    edit_members_keyboard as _edit_members_keyboard,
)
from medication_reminder.telegram.medication_set_views import format_set as _format_set
from medication_reminder.telegram.medication_set_views import format_sets as _format_sets
from medication_reminder.telegram.medication_set_views import members_keyboard as _members_keyboard
from medication_reminder.telegram.medication_set_views import parse_time as _parse_time
from medication_reminder.telegram.medication_set_views import (
    set_actions_keyboard as _set_actions_keyboard,
)
from medication_reminder.telegram.medication_set_views import sets_keyboard as _sets_keyboard
from medication_reminder.telegram.screen import answer_main_screen
from medication_reminder.telegram.service import (
    TelegramApplicationService,
    TimezoneRequiredError,
)
from medication_reminder.telegram.today import show_today_from_callback
from medication_reminder.telegram.transactions import CommitDatabase

_PRESETS = MEDICATION_SET_PRESETS


class CreateSet(StatesGroup):
    members = State()


class EditSet(StatesGroup):
    members = State()


def create_medication_sets_router() -> Router:
    router = Router(name="medication_sets")

    @router.callback_query(F.data.startswith(f"{SetTakeAllCallback.PREFIX}:"))
    async def take_all(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        response: str | None = "Не удалось отметить набор"
        show_alert = False
        try:
            parsed = SetTakeAllCallback.decode(callback.data or "")
            await medication_set_service.take_all(
                callback.from_user.id,
                parsed.set_id,
                parsed.local_date,
            )
            await commit_database()
            await state.clear()
            text, markup = await telegram_service.today_screen(callback.from_user.id)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(text, reply_markup=markup)
            response = None
        except (MedicationSetError, ValueError):
            response = "Набор уже обработан или недоступен"
            show_alert = True
        except TimezoneRequiredError:
            response = "Сначала настройте часовой пояс"
            show_alert = True
        finally:
            await callback.answer(response, show_alert=show_alert)

    @router.message(Command("sets"))
    @router.message(F.text == SETS_BUTTON)
    async def list_message(
        message: Message,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        if message.from_user is None:
            return
        items = await medication_set_service.list(message.from_user.id)
        await answer_main_screen(message, _format_sets(items), _sets_keyboard(items))

    @router.callback_query(F.data == "ms:list")
    async def list_callback(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        await state.clear()
        if isinstance(callback.message, Message):
            items = await medication_set_service.list(callback.from_user.id)
            await callback.message.edit_text(
                _format_sets(items), reply_markup=_sets_keyboard(items)
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("ms:view:"))
    async def view_set(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        try:
            await state.clear()
            set_id = _callback_uuid(callback.data)
            details = await medication_set_service.details(callback.from_user.id, set_id)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    _format_set(details), reply_markup=_set_actions_keyboard(set_id)
                )
            await callback.answer()
        except (MedicationSetError, ValueError):
            await callback.answer("Набор не найден", show_alert=True)

    @router.callback_query(F.data.startswith("ms:new:"))
    async def begin(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        preset = (callback.data or "").rsplit(":", 1)[-1]
        if preset not in _PRESETS:
            await callback.answer("Некорректный набор", show_alert=True)
            return
        regimens = await medication_set_service.available_regimens(callback.from_user.id)
        if not regimens:
            await callback.answer(
                "Нет свободных активных курсов. Сначала добавьте препарат.",
                show_alert=True,
            )
            return
        await state.clear()
        await state.update_data(selected_regimens=[])
        name, start, end = _PRESETS[preset]
        await state.update_data(
            set_name=name,
            window_start=start.strftime("%H:%M"),
            window_end=end.strftime("%H:%M"),
        )
        await state.set_state(CreateSet.members)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Выберите препараты для набора:",
                reply_markup=_members_keyboard(regimens, frozenset()),
            )
        await callback.answer()

    @router.callback_query(CreateSet.members, F.data.startswith("ms:member:"))
    async def toggle(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        try:
            regimen_id = UUID((callback.data or "").rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        data = await state.get_data()
        selected = {
            UUID(str(value)) for value in cast(list[object], data.get("selected_regimens", []))
        }
        selected ^= {regimen_id}
        await state.update_data(selected_regimens=[str(value) for value in selected])
        regimens = await medication_set_service.available_regimens(callback.from_user.id)
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(
                reply_markup=_members_keyboard(regimens, frozenset(selected))
            )
        await callback.answer()

    @router.callback_query(CreateSet.members, F.data == "ms:save")
    async def save(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        data = await state.get_data()
        selected = tuple(
            UUID(str(value)) for value in cast(list[object], data.get("selected_regimens", []))
        )
        if not selected:
            await callback.answer("Выберите хотя бы один препарат", show_alert=True)
            return
        try:
            name = str(data["set_name"])
            start = _parse_time(str(data["window_start"]))
            end = _parse_time(str(data["window_end"]))
            await medication_set_service.create(
                callback.from_user.id,
                name=name,
                window_start=start,
                window_end=end,
                regimen_ids=selected,
            )
            await commit_database()
            await show_today_from_callback(callback, state, telegram_service)
            await callback.answer("Сохранено")
        except (MedicationSetError, KeyError, ValueError):
            await callback.answer("Не удалось создать набор", show_alert=True)

    @router.callback_query(F.data.startswith("ms:edit-members:"))
    async def begin_edit_members(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        try:
            set_id = _callback_uuid(callback.data)
            current = await medication_set_service.details(callback.from_user.id, set_id)
            regimens = await medication_set_service.editable_regimens(callback.from_user.id, set_id)
            selected = frozenset(item.id for item in current.regimens)
            await state.clear()
            await state.update_data(
                set_id=str(set_id), selected_regimens=[str(value) for value in selected]
            )
            await state.set_state(EditSet.members)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Выберите новый состав набора:",
                    reply_markup=_edit_members_keyboard(regimens, selected, set_id),
                )
            await callback.answer()
        except (MedicationSetError, ValueError):
            await callback.answer("Набор не найден", show_alert=True)

    @router.callback_query(EditSet.members, F.data.startswith("ms:edit-member:"))
    async def toggle_edit_member(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        try:
            regimen_id = _callback_uuid(callback.data)
            data = await state.get_data()
            set_id = UUID(str(data["set_id"]))
            selected = {UUID(str(value)) for value in cast(list[object], data["selected_regimens"])}
            selected ^= {regimen_id}
            await state.update_data(selected_regimens=[str(value) for value in selected])
            regimens = await medication_set_service.editable_regimens(callback.from_user.id, set_id)
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(
                    reply_markup=_edit_members_keyboard(regimens, frozenset(selected), set_id)
                )
            await callback.answer()
        except (KeyError, MedicationSetError, ValueError):
            await callback.answer("Не удалось обновить выбор", show_alert=True)

    @router.callback_query(EditSet.members, F.data == "ms:edit-members-save")
    async def save_edit_members(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        data = await state.get_data()
        selected = tuple(
            UUID(str(value)) for value in cast(list[object], data.get("selected_regimens", []))
        )
        if not selected:
            await callback.answer("В наборе должен остаться хотя бы один препарат", show_alert=True)
            return
        try:
            set_id = UUID(str(data["set_id"]))
            current = await medication_set_service.details(callback.from_user.id, set_id)
            value = current.medication_set
            await medication_set_service.update(
                callback.from_user.id,
                set_id=set_id,
                name=value.name,
                window_start=value.window_start,
                window_end=value.window_end,
                regimen_ids=selected,
            )
            await commit_database()
            await show_today_from_callback(callback, state, telegram_service)
            await callback.answer("Сохранено")
        except (KeyError, MedicationSetError, ValueError):
            await callback.answer("Не удалось сохранить состав", show_alert=True)

    @router.callback_query(F.data.startswith("ms:delete-ask:"))
    async def confirm_delete(callback: CallbackQuery) -> None:
        try:
            set_id = _callback_uuid(callback.data)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Удалить набор? Курсы и их графики останутся без изменений.",
                    reply_markup=_delete_confirmation_keyboard(set_id),
                )
            await callback.answer()
        except ValueError:
            await callback.answer("Некорректный набор", show_alert=True)

    @router.callback_query(F.data.startswith("ms:delete-yes:"))
    async def delete_set(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        try:
            await medication_set_service.delete(
                callback.from_user.id, _callback_uuid(callback.data)
            )
            await commit_database()
            await show_today_from_callback(callback, state, telegram_service)
            await callback.answer("Набор удалён")
        except (MedicationSetError, ValueError):
            await callback.answer("Набор уже удалён или недоступен", show_alert=True)

    @router.callback_query(F.data == "ms:cancel")
    async def cancel(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await show_today_from_callback(callback, state, telegram_service)
        await callback.answer("Отменено")

    return router


def _callback_uuid(value: str | None) -> UUID:
    if value is None:
        raise ValueError("Callback data is required")
    return UUID(value.rsplit(":", 1)[-1])
