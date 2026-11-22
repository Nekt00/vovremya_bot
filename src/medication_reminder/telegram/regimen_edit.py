from datetime import date
from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from medication_reminder.families.service import FamilyAccessError
from medication_reminder.regimens.application.revisions import (
    NoFutureEventsError,
    RegimenRevisionConflictError,
    RegimenRevisionError,
    RegimenRevisionNotFoundError,
    RemainingIntakesTooSmallError,
)
from medication_reminder.regimens.application.use_cases import RegimenNotFoundError
from medication_reminder.regimens.domain.regimen import MealTiming, RegimenStatus
from medication_reminder.telegram.callbacks import RegimenAction, RegimenCallback
from medication_reminder.telegram.regimen_edit_forms import common_time as _common_time
from medication_reminder.telegram.regimen_edit_forms import dose_keyboard as _dose_keyboard
from medication_reminder.telegram.regimen_edit_forms import (
    duration_kind_keyboard as _duration_kind_keyboard,
)
from medication_reminder.telegram.regimen_edit_forms import ending_values as _ending_values
from medication_reminder.telegram.regimen_edit_forms import (
    meal_timing_keyboard as _meal_timing_keyboard,
)
from medication_reminder.telegram.regimen_edit_forms import (
    meal_timing_value as _meal_timing_value,
)
from medication_reminder.telegram.regimen_edit_forms import mode_keyboard as _mode_keyboard
from medication_reminder.telegram.regimen_edit_forms import revision_values as _revision_values
from medication_reminder.telegram.regimen_edit_forms import (
    schedule_keyboard as _schedule_keyboard,
)
from medication_reminder.telegram.regimen_edit_forms import selected_times as _selected_times
from medication_reminder.telegram.regimen_edit_forms import summary_keyboard as _summary_keyboard
from medication_reminder.telegram.regimen_edit_forms import summary_text as _summary_text
from medication_reminder.telegram.regimen_edit_forms import times_keyboard as _times_keyboard
from medication_reminder.telegram.regimen_edit_forms import (
    weekdays_keyboard as _weekdays_keyboard,
)
from medication_reminder.telegram.regimen_service import TelegramRegimenService
from medication_reminder.telegram.service import TelegramApplicationService
from medication_reminder.telegram.today import show_today_from_callback
from medication_reminder.telegram.transactions import CommitDatabase
from medication_reminder.telegram.wizard_models import (
    MAX_INTERVAL_DAYS,
    MAX_TOTAL_INTAKES,
    ScheduleKind,
    WizardValidationError,
    parse_dose_amount,
    parse_local_date,
    parse_positive_int,
    parse_quick_dose,
    parse_times,
    toggle_time,
    toggle_weekday,
)

_PREFIX = "re"
_WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


class EditRegimen(StatesGroup):
    mode = State()
    dose = State()
    meal_timing = State()
    duration_kind = State()
    duration = State()
    schedule_kind = State()
    interval = State()
    weekdays = State()
    times = State()
    summary = State()
    saving = State()


def create_regimen_edit_router() -> Router:
    router = Router(name="regimen_edit")

    @router.callback_query(F.data.startswith("rg:e:"))
    async def begin(
        callback: CallbackQuery,
        state: FSMContext,
        regimen_service: TelegramRegimenService,
    ) -> None:
        try:
            parsed = RegimenCallback.decode(callback.data or "")
            if parsed.action is not RegimenAction.EDIT:
                raise ValueError
            details = await regimen_service.details(callback.from_user.id, parsed.regimen_id)
            if not details.can_manage:
                raise FamilyAccessError
            if details.regimen.status is not RegimenStatus.ACTIVE:
                await callback.answer("Изменять можно только активный курс", show_alert=True)
                return
        except (
            ValueError,
            FamilyAccessError,
            RegimenNotFoundError,
            RegimenRevisionNotFoundError,
        ):
            await callback.answer("Курс не найден", show_alert=True)
            return
        await state.clear()
        await state.update_data(regimen_id=str(parsed.regimen_id))
        await state.set_state(EditRegimen.mode)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Что изменить в будущих приёмах?",
                reply_markup=_mode_keyboard(),
            )
        await callback.answer()

    @router.callback_query(EditRegimen.mode, F.data.startswith(f"{_PREFIX}:mode:"))
    async def choose_mode(callback: CallbackQuery, state: FSMContext) -> None:
        mode = (callback.data or "").rsplit(":", 1)[-1]
        if mode not in {"dose", "meal", "schedule", "both", "duration"}:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(edit_mode=mode)
        if mode == "meal":
            await state.set_state(EditRegimen.meal_timing)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Как препарат связан с приёмом пищи?",
                    reply_markup=_meal_timing_keyboard(),
                )
        elif mode == "duration":
            await state.set_state(EditRegimen.duration_kind)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Как изменить длительность курса?",
                    reply_markup=_duration_kind_keyboard(),
                )
        elif mode in {"dose", "both"}:
            await state.set_state(EditRegimen.dose)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Выберите новую дозировку или введите свою:",
                    reply_markup=_dose_keyboard(),
                )
        else:
            await _ask_schedule_kind(callback, state)
            return
        await callback.answer()

    @router.callback_query(
        EditRegimen.meal_timing,
        F.data.startswith(f"{_PREFIX}:meal:"),
    )
    async def meal_timing(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            value = MealTiming((callback.data or "").rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(new_meal_timing=value.value)
        await _show_summary_callback(callback, state)

    @router.callback_query(
        EditRegimen.duration_kind,
        F.data.startswith(f"{_PREFIX}:duration:"),
    )
    async def duration_kind(callback: CallbackQuery, state: FSMContext) -> None:
        kind = (callback.data or "").rsplit(":", 1)[-1]
        if kind not in {"count", "date"}:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(duration_kind=kind)
        await state.set_state(EditRegimen.duration)
        if isinstance(callback.message, Message):
            prompt = (
                "Введите количество оставшихся приёмов:"
                if kind == "count"
                else "Введите новую дату окончания в формате ДД.ММ.ГГГГ:"
            )
            await callback.message.edit_text(prompt)
        await callback.answer()

    @router.message(EditRegimen.duration)
    async def duration(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            if data.get("duration_kind") == "count":
                value: int | date = parse_positive_int(
                    message.text or "",
                    maximum=MAX_TOTAL_INTAKES,
                    label="Количество приёмов",
                )
                await state.update_data(remaining_intakes=value)
            else:
                value = parse_local_date(message.text or "")
                await state.update_data(end_date=value.isoformat())
        except WizardValidationError as error:
            await message.answer(str(error))
            return
        await _show_summary_message(message, state)

    @router.callback_query(EditRegimen.dose, F.data.startswith(f"{_PREFIX}:dose:"))
    async def quick_dose(callback: CallbackQuery, state: FSMContext) -> None:
        value = (callback.data or "").rsplit(":", 1)[-1]
        if value == "custom":
            if isinstance(callback.message, Message):
                await callback.message.edit_text("Введите новую дозировку числом, например 1,5:")
            await callback.answer()
            return
        try:
            dose = parse_quick_dose(value)
        except WizardValidationError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(new_dose=str(dose))
        await _after_dose(callback, state)

    @router.message(EditRegimen.dose)
    async def custom_dose(message: Message, state: FSMContext) -> None:
        try:
            dose = parse_dose_amount(message.text or "")
        except WizardValidationError as error:
            await message.answer(str(error))
            return
        await state.update_data(new_dose=str(dose))
        data = await state.get_data()
        if data.get("edit_mode") == "both":
            await state.set_state(EditRegimen.schedule_kind)
            await message.answer("Выберите новый график:", reply_markup=_schedule_keyboard())
        else:
            await _show_summary_message(message, state)

    @router.callback_query(
        EditRegimen.schedule_kind,
        F.data.startswith(f"{_PREFIX}:kind:"),
    )
    async def schedule_kind(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            kind = ScheduleKind((callback.data or "").rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(schedule_kind=kind.value)
        if kind is ScheduleKind.INTERVAL:
            await state.set_state(EditRegimen.interval)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    f"Введите интервал в днях — от 1 до {MAX_INTERVAL_DAYS}:"
                )
        elif kind is ScheduleKind.WEEKDAYS:
            await state.update_data(weekdays=[])
            await state.set_state(EditRegimen.weekdays)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Выберите дни недели:",
                    reply_markup=_weekdays_keyboard(frozenset()),
                )
        elif kind is ScheduleKind.WEEKLY:
            await state.update_data(time_target="workdays", selected_times=[])
            await state.set_state(EditRegimen.times)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Во сколько напоминать <b>в будни (Пн–Пт)</b>?",
                    reply_markup=_times_keyboard(()),
                )
        else:
            await _ask_times(callback, state)
            return
        await callback.answer()

    @router.message(EditRegimen.interval)
    async def interval(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_int(
                message.text or "",
                maximum=MAX_INTERVAL_DAYS,
                label="Интервал",
            )
        except WizardValidationError as error:
            await message.answer(str(error))
            return
        await state.update_data(every_days=value, selected_times=[])
        await state.set_state(EditRegimen.times)
        await message.answer("Выберите время:", reply_markup=_times_keyboard(()))

    @router.callback_query(
        EditRegimen.weekdays,
        F.data.startswith(f"{_PREFIX}:weekday:"),
    )
    async def weekdays(callback: CallbackQuery, state: FSMContext) -> None:
        suffix = (callback.data or "").rsplit(":", 1)[-1]
        data = await state.get_data()
        selected = frozenset(int(value) for value in data.get("weekdays", []))
        if suffix == "done":
            if not selected:
                await callback.answer("Выберите хотя бы один день", show_alert=True)
                return
            await _ask_times(callback, state)
            return
        try:
            weekday = int(suffix)
            selected = toggle_weekday(selected, weekday)
        except (ValueError, WizardValidationError):
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(weekdays=sorted(selected))
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=_weekdays_keyboard(selected))
        await callback.answer()

    @router.callback_query(EditRegimen.times, F.data.startswith(f"{_PREFIX}:time:"))
    async def times(callback: CallbackQuery, state: FSMContext) -> None:
        suffix = (callback.data or "").rsplit(":", 1)[-1]
        if suffix == "custom":
            data = await state.get_data()
            target = data.get("time_target")
            label = (
                " для будней"
                if target == "workdays"
                else " для выходных"
                if target == "weekends"
                else ""
            )
            if isinstance(callback.message, Message):
                await callback.message.edit_text(f"Введите время{label} вручную: 06:00, 21:00")
            await callback.answer()
            return
        data = await state.get_data()
        try:
            selected = _selected_times(data)
            if suffix == "done":
                if not selected:
                    await callback.answer("Выберите хотя бы одно время", show_alert=True)
                    return
                serialized = ", ".join(value.strftime("%H:%M") for value in selected)
                if data.get("schedule_kind") == ScheduleKind.WEEKLY.value:
                    if data.get("time_target") == "workdays":
                        await state.update_data(
                            workday_times=serialized,
                            time_target="weekends",
                            selected_times=[],
                        )
                        if isinstance(callback.message, Message):
                            await callback.message.edit_text(
                                "Во сколько напоминать <b>в выходные (Сб–Вс)</b>?",
                                reply_markup=_times_keyboard(()),
                            )
                        await callback.answer()
                        return
                    await state.update_data(weekend_times=serialized)
                else:
                    await state.update_data(times=serialized)
                await _show_summary_callback(callback, state)
                return
            selected = toggle_time(selected, _common_time(suffix))
        except WizardValidationError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(selected_times=[value.strftime("%H:%M") for value in selected])
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=_times_keyboard(selected))
        await callback.answer()

    @router.message(EditRegimen.times)
    async def custom_times(message: Message, state: FSMContext) -> None:
        try:
            values = parse_times(message.text or "")
        except WizardValidationError as error:
            await message.answer(str(error))
            return
        serialized = ", ".join(value.strftime("%H:%M") for value in values)
        data = await state.get_data()
        if data.get("schedule_kind") == ScheduleKind.WEEKLY.value:
            if data.get("time_target") == "workdays":
                await state.update_data(
                    workday_times=serialized,
                    time_target="weekends",
                    selected_times=[],
                )
                await message.answer(
                    "Во сколько напоминать <b>в выходные (Сб–Вс)</b>?",
                    reply_markup=_times_keyboard(()),
                )
                return
            await state.update_data(weekend_times=serialized)
        else:
            await state.update_data(times=serialized)
        await _show_summary_message(message, state)

    @router.callback_query(EditRegimen.summary, F.data == f"{_PREFIX}:save")
    async def save(
        callback: CallbackQuery,
        state: FSMContext,
        regimen_service: TelegramRegimenService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        await state.set_state(EditRegimen.saving)
        try:
            data = await state.get_data()
            regimen_id = UUID(str(data["regimen_id"]))
            dose, rule = _revision_values(data)
            meal_timing = _meal_timing_value(data)
            remaining_intakes, end_date = _ending_values(data)
            await regimen_service.revise(
                callback.from_user.id,
                regimen_id,
                dose_amount=dose,
                rule=rule,
                meal_timing=meal_timing,
                remaining_intakes=remaining_intakes,
                end_date=end_date,
            )
            await commit_database()
            await show_today_from_callback(callback, state, telegram_service)
            await callback.answer("Сохранено")
        except NoFutureEventsError:
            await state.set_state(EditRegimen.summary)
            await callback.answer("Нет будущих приёмов для изменения", show_alert=True)
        except (RegimenRevisionNotFoundError, RegimenRevisionConflictError):
            await state.clear()
            await callback.answer(
                "Курс уже изменился. Откройте список заново.", show_alert=True
            )
        except RemainingIntakesTooSmallError as error:
            await state.set_state(EditRegimen.summary)
            await callback.answer(
                f"Сейчас ожидают отметки: {error.pending_count}. Укажите не меньше.",
                show_alert=True,
            )
        except (
            FamilyAccessError,
            RegimenRevisionError,
            WizardValidationError,
            KeyError,
            ValueError,
        ):
            await state.set_state(EditRegimen.summary)
            await callback.answer("Не удалось пересчитать график", show_alert=True)

    @router.callback_query(F.data == f"{_PREFIX}:cancel")
    async def cancel(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await show_today_from_callback(callback, state, telegram_service)
        await callback.answer("Отменено")

    @router.callback_query(F.data.startswith(f"{_PREFIX}:"))
    async def stale(callback: CallbackQuery) -> None:
        await callback.answer("Эта кнопка устарела", show_alert=True)

    return router


async def _after_dose(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("edit_mode") == "both":
        await _ask_schedule_kind(callback, state)
        return
    await _show_summary_callback(callback, state)


async def _ask_schedule_kind(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditRegimen.schedule_kind)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Выберите новый график:",
            reply_markup=_schedule_keyboard(),
        )
    await callback.answer()


async def _ask_times(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(selected_times=[])
    await state.set_state(EditRegimen.times)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Выберите время:", reply_markup=_times_keyboard(()))
    await callback.answer()


async def _show_summary_callback(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = _summary_text(data)
    await state.set_state(EditRegimen.summary)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=_summary_keyboard())
    await callback.answer()


async def _show_summary_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = _summary_text(data)
    await state.set_state(EditRegimen.summary)
    await message.answer(text, reply_markup=_summary_keyboard())
