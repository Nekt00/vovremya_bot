from datetime import time, timedelta
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from medication_reminder.families.service import FamilyAccessError, FamilyService
from medication_reminder.medication_sets.application import MedicationSetError
from medication_reminder.regimens.domain.regimen import MealTiming, MedicationForm
from medication_reminder.telegram.handlers import request_timezone_setup
from medication_reminder.telegram.keyboards import ADD_BUTTON
from medication_reminder.telegram.medication_set_service import TelegramMedicationSetService
from medication_reminder.telegram.service import TelegramApplicationService, TimezoneRequiredError
from medication_reminder.telegram.today import (
    show_today_from_callback,
    show_today_from_message,
)
from medication_reminder.telegram.transactions import CommitDatabase
from medication_reminder.telegram.wizard_models import (
    COMMON_TIMES,
    MAX_INTERVAL_DAYS,
    MAX_TOTAL_INTAKES,
    EndingKind,
    ScheduleKind,
    WizardValidationError,
    command_from_state,
    format_summary,
    parse_dose_amount,
    parse_dose_unit,
    parse_local_date,
    parse_medication_name,
    parse_positive_int,
    parse_quick_dose,
    parse_times,
    toggle_time,
    toggle_weekday,
)
from medication_reminder.telegram.wizard_service import (
    StaleStartDateError,
    WizardApplicationService,
)
from medication_reminder.telegram.wizard_ui import CANCEL_BUTTON
from medication_reminder.telegram.wizard_ui import FORM_LABELS as _FORM_LABELS
from medication_reminder.telegram.wizard_ui import SET_PRESETS as _SET_PRESETS
from medication_reminder.telegram.wizard_ui import UNIT_PRESETS as _UNIT_PRESETS
from medication_reminder.telegram.wizard_ui import cancel_reply as _cancel_reply
from medication_reminder.telegram.wizard_ui import dose_amount_keyboard as _dose_amount_keyboard
from medication_reminder.telegram.wizard_ui import ending_keyboard as _ending_keyboard
from medication_reminder.telegram.wizard_ui import form_keyboard as _form_keyboard
from medication_reminder.telegram.wizard_ui import meal_timing_keyboard as _meal_timing_keyboard
from medication_reminder.telegram.wizard_ui import (
    reminder_target_keyboard as _reminder_target_keyboard,
)
from medication_reminder.telegram.wizard_ui import schedule_keyboard as _schedule_keyboard
from medication_reminder.telegram.wizard_ui import start_date_keyboard as _start_date_keyboard
from medication_reminder.telegram.wizard_ui import summary_keyboard as _summary_keyboard
from medication_reminder.telegram.wizard_ui import times_keyboard as _times_keyboard
from medication_reminder.telegram.wizard_ui import unit_keyboard as _unit_keyboard
from medication_reminder.telegram.wizard_ui import weekdays_keyboard as _weekdays_keyboard

_PREFIX = "w"


class AddRegimen(StatesGroup):
    recipient = State()
    name = State()
    form = State()
    dose_amount = State()
    dose_unit = State()
    custom_unit = State()
    meal_timing = State()
    start_date = State()
    reminder_target = State()
    schedule_kind = State()
    interval = State()
    weekdays = State()
    times = State()
    ending = State()
    total_intakes = State()
    end_date = State()
    summary = State()
    saving = State()


def create_wizard_router(*, mini_app_url: str | None) -> Router:
    router = Router(name="add_regimen_wizard")

    @router.message(Command("cancel"))
    @router.message(F.text == CANCEL_BUTTON)
    async def cancel(
        message: Message,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await cancel_wizard(state)
        await show_today_from_message(
            message,
            state,
            telegram_service,
            restore_main_menu=True,
        )

    @router.callback_query(F.data == f"{_PREFIX}:cancel")
    async def cancel_callback(
        callback: CallbackQuery,
        state: FSMContext,
        telegram_service: TelegramApplicationService,
    ) -> None:
        await show_today_from_callback(
            callback,
            state,
            telegram_service,
            restore_main_menu=True,
        )
        await callback.answer("Отменено")

    @router.message(Command("add"))
    @router.message(F.text == ADD_BUTTON)
    async def begin(
        message: Message,
        state: FSMContext,
        wizard_service: WizardApplicationService,
        family_service: FamilyService,
        telegram_service: TelegramApplicationService,
        telegram_user_id: int | None = None,
    ) -> None:
        telegram_id = telegram_user_id if telegram_user_id is not None else _telegram_id(message)
        if telegram_id is None:
            return
        try:
            await wizard_service.require_timezone(telegram_id)
        except TimezoneRequiredError:
            await request_timezone_setup(message, state, mini_app_url)
            return
        targets = await family_service.list_targets(telegram_id)
        can_manage_self = await family_service.can_manage_personal_regimens(telegram_id)
        if not targets:
            if not can_manage_self:
                await message.answer("Ваша роль разрешает только отмечать назначенные приёмы.")
                await show_today_from_message(message, state, telegram_service)
                return
            await state.update_data(target_telegram_user_id=telegram_id)
            await _begin_wizard(message, state, keep_target=True)
            return
        await restart_wizard(state)
        await state.update_data(
            family_targets=[
                {
                    "group_id": str(target.group_id),
                    "user_id": str(target.user_id),
                }
                for target in targets
            ]
        )
        await state.set_state(AddRegimen.recipient)
        rows = []
        if can_manage_self:
            rows.append(
                [InlineKeyboardButton(text="👤 Себе", callback_data=f"{_PREFIX}:recipient:self")]
            )
        rows.extend(
            [
                InlineKeyboardButton(
                    text=f"👨‍👩‍👧 {target.display_name} · {target.group_name}",
                    callback_data=f"{_PREFIX}:recipient:{index}",
                )
            ]
            for index, target in enumerate(targets)
        )
        await message.answer(
            "Для кого создать курс?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    @router.callback_query(F.data == "nav:add")
    async def begin_from_callback(
        callback: CallbackQuery,
        state: FSMContext,
        wizard_service: WizardApplicationService,
        family_service: FamilyService,
        telegram_service: TelegramApplicationService,
    ) -> None:
        if isinstance(callback.message, Message):
            await begin(
                callback.message,
                state,
                wizard_service,
                family_service,
                telegram_service,
                telegram_user_id=callback.from_user.id,
            )
        await callback.answer()

    @router.callback_query(AddRegimen.recipient, F.data.startswith(f"{_PREFIX}:recipient:"))
    async def select_recipient(
        callback: CallbackQuery,
        state: FSMContext,
        family_service: FamilyService,
    ) -> None:
        value = (callback.data or "").removeprefix(f"{_PREFIX}:recipient:")
        try:
            if value == "self":
                await state.update_data(target_telegram_user_id=callback.from_user.id)
            else:
                data = await state.get_data()
                stored_targets = data.get("family_targets", [])
                stored_target = stored_targets[int(value)]
                target = await family_service.resolve_target(
                    callback.from_user.id,
                    target_user_id=UUID(str(stored_target["user_id"])),
                    group_id=UUID(str(stored_target["group_id"])),
                )
                if target.timezone is None:
                    await callback.answer(
                        "Участнику нужно сначала открыть бота и настроить часовой пояс",
                        show_alert=True,
                    )
                    return
                await state.update_data(
                    target_telegram_user_id=target.telegram_user_id,
                    family_target_user_id=str(target.user_id),
                    family_group_id=str(target.group_id),
                    family_target_name=target.display_name,
                )
        except (ValueError, FamilyAccessError):
            await callback.answer("Участник больше недоступен", show_alert=True)
            return
        await state.set_state(AddRegimen.name)
        if isinstance(callback.message, Message):
            await callback.message.edit_text("Введите название препарата:")
        await callback.answer()

    @router.message(AddRegimen.name)
    async def name(message: Message, state: FSMContext) -> None:
        try:
            value = parse_medication_name(message.text or "")
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_cancel_reply())
            return
        await state.update_data(medication_name=value)
        await state.set_state(AddRegimen.form)
        await message.answer("Выберите форму препарата:", reply_markup=_form_keyboard())

    @router.callback_query(AddRegimen.form, F.data.startswith(f"{_PREFIX}:form:"))
    async def form(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            value = MedicationForm((callback.data or "").rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(medication_form=value.value)
        await state.set_state(AddRegimen.dose_amount)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(f"Форма: {_FORM_LABELS[value]}")
            await callback.message.answer(
                "Выберите количество за один приём или введите своё. "
                "Это варианты ввода, а не медицинские рекомендации.",
                reply_markup=_dose_amount_keyboard(),
            )
        await callback.answer()

    @router.callback_query(AddRegimen.dose_amount, F.data.startswith(f"{_PREFIX}:dose:"))
    async def dose_amount_quick(callback: CallbackQuery, state: FSMContext) -> None:
        suffix = (callback.data or "").rsplit(":", 1)[-1]
        if suffix == "custom":
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Введите количество числом, например <code>1</code> или <code>2,5</code>:"
                )
            await callback.answer()
            return
        try:
            value = parse_quick_dose(suffix)
            data = await state.get_data()
            medication_form = MedicationForm(str(data["medication_form"]))
        except (WizardValidationError, ValueError, KeyError):
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(dose_amount=str(value))
        await state.set_state(AddRegimen.dose_unit)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Выберите единицу дозы:", reply_markup=_unit_keyboard(medication_form)
            )
        await callback.answer()

    @router.message(AddRegimen.dose_amount)
    async def dose_amount(message: Message, state: FSMContext) -> None:
        try:
            value = parse_dose_amount(message.text or "")
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_cancel_reply())
            return
        data = await state.get_data()
        medication_form = MedicationForm(str(data["medication_form"]))
        await state.update_data(dose_amount=str(value))
        await state.set_state(AddRegimen.dose_unit)
        await message.answer("Выберите единицу дозы:", reply_markup=_unit_keyboard(medication_form))

    @router.callback_query(AddRegimen.dose_unit, F.data.startswith(f"{_PREFIX}:unit:"))
    async def dose_unit(callback: CallbackQuery, state: FSMContext) -> None:
        suffix = (callback.data or "").rsplit(":", 1)[-1]
        if suffix == "other":
            await state.set_state(AddRegimen.custom_unit)
            if isinstance(callback.message, Message):
                await callback.message.edit_text("Введите единицу дозы, например <code>мг</code>:")
            await callback.answer()
            return
        try:
            index = int(suffix)
            data = await state.get_data()
            medication_form = MedicationForm(str(data["medication_form"]))
            value = _UNIT_PRESETS[medication_form][index]
        except (ValueError, KeyError, IndexError):
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(dose_unit=value)
        await _ask_meal_timing(callback, state)

    @router.message(AddRegimen.custom_unit)
    async def custom_unit(message: Message, state: FSMContext) -> None:
        try:
            value = parse_dose_unit(message.text or "")
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_cancel_reply())
            return
        await state.update_data(dose_unit=value)
        await state.set_state(AddRegimen.meal_timing)
        await message.answer(
            "Как принимать относительно еды?",
            reply_markup=_meal_timing_keyboard(),
        )

    @router.callback_query(AddRegimen.meal_timing, F.data.startswith(f"{_PREFIX}:meal:"))
    async def meal_timing(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            value = MealTiming((callback.data or "").rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(meal_timing=value.value)
        await _ask_start_date(callback, state)

    @router.callback_query(AddRegimen.start_date, F.data.startswith(f"{_PREFIX}:start:"))
    async def start_date_shortcut(
        callback: CallbackQuery,
        state: FSMContext,
        wizard_service: WizardApplicationService,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        suffix = (callback.data or "").rsplit(":", 1)[-1]
        if suffix not in {"today", "tomorrow"}:
            await callback.answer("Некорректная кнопка")
            return
        data = await state.get_data()
        selected = await wizard_service.local_today(
            callback.from_user.id,
            int(data.get("target_telegram_user_id", callback.from_user.id)),
        )
        if suffix == "tomorrow":
            selected += timedelta(days=1)
        await state.update_data(start_date=selected.strftime("%d.%m.%Y"))
        await _ask_reminder_target_callback(callback, state, medication_set_service)

    @router.message(AddRegimen.start_date)
    async def start_date_manual(
        message: Message,
        state: FSMContext,
        wizard_service: WizardApplicationService,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        telegram_id = _telegram_id(message)
        if telegram_id is None:
            return
        try:
            value = parse_local_date(message.text or "")
            data = await state.get_data()
            if value < await wizard_service.local_today(
                telegram_id,
                int(data.get("target_telegram_user_id", telegram_id)),
            ):
                raise WizardValidationError("Дата начала не может быть в прошлом")
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_start_date_keyboard())
            return
        await state.update_data(start_date=value.strftime("%d.%m.%Y"))
        await state.set_state(AddRegimen.reminder_target)
        data = await state.get_data()
        sets = await medication_set_service.list(
            int(data.get("target_telegram_user_id", telegram_id))
        )
        await message.answer(
            "Куда добавить препарат?",
            reply_markup=_reminder_target_keyboard(sets),
        )

    @router.callback_query(AddRegimen.reminder_target, F.data.startswith(f"{_PREFIX}:target:"))
    async def reminder_target(
        callback: CallbackQuery,
        state: FSMContext,
        medication_set_service: TelegramMedicationSetService,
    ) -> None:
        suffix = (callback.data or "").removeprefix(f"{_PREFIX}:target:")
        if suffix == "exact":
            await state.update_data(reminder_mode="exact")
            await state.set_state(AddRegimen.schedule_kind)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Выберите периодичность:", reply_markup=_schedule_keyboard()
                )
            await callback.answer()
            return
        try:
            if suffix in _SET_PRESETS:
                name, start, end = _SET_PRESETS[suffix]
                await _store_set_target(state, None, name, start, end)
            else:
                data = await state.get_data()
                details = await medication_set_service.details(
                    int(data.get("target_telegram_user_id", callback.from_user.id)),
                    UUID(suffix),
                )
                value = details.medication_set
                await _store_set_target(
                    state,
                    value.id,
                    value.name,
                    value.window_start,
                    value.window_end,
                )
        except (MedicationSetError, ValueError):
            await callback.answer("Набор больше недоступен", show_alert=True)
            return
        await state.set_state(AddRegimen.schedule_kind)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Выберите периодичность приёма:",
                reply_markup=_schedule_keyboard(allow_weekly=False),
            )
        await callback.answer()

    @router.callback_query(AddRegimen.schedule_kind, F.data.startswith(f"{_PREFIX}:schedule:"))
    async def schedule_kind(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            kind = ScheduleKind((callback.data or "").rsplit(":", 1)[-1])
            data = await state.get_data()
            uses_set = data.get("reminder_mode") == "set"
            if uses_set and kind is ScheduleKind.WEEKLY:
                raise ValueError
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(schedule_kind=kind.value)
        if kind is ScheduleKind.INTERVAL:
            await state.set_state(AddRegimen.interval)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    f"Введите интервал в днях — от 1 до {MAX_INTERVAL_DAYS}:"
                )
        elif kind is ScheduleKind.WEEKDAYS:
            await state.update_data(weekdays=[])
            await state.set_state(AddRegimen.weekdays)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Выберите дни недели:", reply_markup=_weekdays_keyboard(frozenset())
                )
        elif kind is ScheduleKind.WEEKLY:
            await state.update_data(time_target="workdays", selected_times=[])
            await state.set_state(AddRegimen.times)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "Во сколько напоминать <b>в будни (Пн–Пт)</b>?",
                    reply_markup=_times_keyboard(()),
                )
        else:
            if uses_set:
                await _ask_ending_callback(callback, state)
            else:
                await _ask_times_callback(callback, state)
            return
        await callback.answer()

    @router.message(AddRegimen.interval)
    async def interval(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_int(
                message.text or "", maximum=MAX_INTERVAL_DAYS, label="Интервал"
            )
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_cancel_reply())
            return
        await state.update_data(every_days=value)
        if (await state.get_data()).get("reminder_mode") == "set":
            await _ask_ending_message(message, state)
        else:
            await state.set_state(AddRegimen.times)
            await state.update_data(selected_times=[])
            await message.answer(
                "Выберите одно или несколько времён:",
                reply_markup=_times_keyboard(()),
            )

    @router.callback_query(AddRegimen.weekdays, F.data.startswith(f"{_PREFIX}:weekday:"))
    async def weekday_toggle(callback: CallbackQuery, state: FSMContext) -> None:
        suffix = (callback.data or "").rsplit(":", 1)[-1]
        data = await state.get_data()
        selected = {int(value) for value in data.get("weekdays", [])}
        if suffix == "done":
            if not selected:
                await callback.answer("Выберите хотя бы один день", show_alert=True)
                return
            if data.get("reminder_mode") == "set":
                await _ask_ending_callback(callback, state)
            else:
                await _ask_times_callback(callback, state)
            return
        try:
            weekday = int(suffix)
            if weekday not in range(1, 8):
                raise ValueError
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        selected = set(toggle_weekday(frozenset(selected), weekday))
        await state.update_data(weekdays=sorted(selected))
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(
                reply_markup=_weekdays_keyboard(frozenset(selected))
            )
        await callback.answer()

    @router.callback_query(AddRegimen.times, F.data.startswith(f"{_PREFIX}:time:"))
    async def time_toggle(callback: CallbackQuery, state: FSMContext) -> None:
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
                await callback.message.edit_text(
                    f"Введите время{label} вручную: <code>05:00, 06:00</code>"
                )
            await callback.answer()
            return
        data = await state.get_data()
        try:
            selected = (
                parse_times(", ".join(str(value) for value in data.get("selected_times", [])))
                if data.get("selected_times")
                else ()
            )
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
                await state.set_state(AddRegimen.ending)
                if isinstance(callback.message, Message):
                    await callback.message.edit_text(
                        "Как завершить курс?", reply_markup=_ending_keyboard()
                    )
                await callback.answer()
                return
            value = _common_time_from_callback(suffix)
            selected = toggle_time(selected, value)
        except WizardValidationError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(selected_times=[value.strftime("%H:%M") for value in selected])
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=_times_keyboard(selected))
        await callback.answer()

    @router.message(AddRegimen.times)
    async def times(message: Message, state: FSMContext) -> None:
        try:
            value = parse_times(message.text or "")
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_cancel_reply())
            return
        serialized = ", ".join(item.strftime("%H:%M") for item in value)
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
        await state.set_state(AddRegimen.ending)
        await message.answer("Как завершить курс?", reply_markup=_ending_keyboard())

    @router.callback_query(AddRegimen.ending, F.data.startswith(f"{_PREFIX}:ending:"))
    async def ending(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            kind = EndingKind((callback.data or "").rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer("Некорректная кнопка")
            return
        await state.update_data(ending_kind=kind.value)
        if kind is EndingKind.TOTAL_INTAKES:
            await state.set_state(AddRegimen.total_intakes)
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    f"Введите количество приёмов — от 1 до {MAX_TOTAL_INTAKES}:"
                )
        elif kind is EndingKind.END_DATE:
            await state.set_state(AddRegimen.end_date)
            if isinstance(callback.message, Message):
                await callback.message.edit_text("Введите дату окончания ДД.ММ.ГГГГ:")
        else:
            await _show_summary(callback, state)
            return
        await callback.answer()

    @router.message(AddRegimen.total_intakes)
    async def total_intakes(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_int(
                message.text or "",
                maximum=MAX_TOTAL_INTAKES,
                label="Количество приёмов",
            )
            await state.update_data(total_intakes=value)
            command = command_from_state(await state.get_data())
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_cancel_reply())
            return
        await state.set_state(AddRegimen.summary)
        await message.answer(format_summary(command), reply_markup=_summary_keyboard())

    @router.message(AddRegimen.end_date)
    async def end_date(message: Message, state: FSMContext) -> None:
        try:
            value = parse_local_date(message.text or "")
            await state.update_data(end_date=value.strftime("%d.%m.%Y"))
            command = command_from_state(await state.get_data())
        except WizardValidationError as error:
            await message.answer(str(error), reply_markup=_cancel_reply())
            return
        await state.set_state(AddRegimen.summary)
        await message.answer(format_summary(command), reply_markup=_summary_keyboard())

    @router.callback_query(AddRegimen.summary, F.data == f"{_PREFIX}:restart")
    async def restart(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        await restart_wizard(state)
        await state.update_data(
            **{
                key: value
                for key, value in data.items()
                if key.startswith("target_") or key.startswith("family_")
            }
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text("Начинаем заново.")
            await callback.message.answer(
                "Введите название препарата:", reply_markup=_cancel_reply()
            )
        await callback.answer()

    @router.callback_query(AddRegimen.summary, F.data == f"{_PREFIX}:save")
    async def confirm(
        callback: CallbackQuery,
        state: FSMContext,
        wizard_service: WizardApplicationService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        response = "Не удалось сохранить"
        saved = False
        try:
            command = command_from_state(await state.get_data())
        except WizardValidationError as error:
            await callback.answer(f"Проверьте данные: {error}", show_alert=True)
            return
        await state.set_state(AddRegimen.saving)
        try:
            data = await state.get_data()
            await wizard_service.save(
                callback.from_user.id,
                command,
                target_user_id=(
                    UUID(str(data["family_target_user_id"]))
                    if data.get("family_target_user_id")
                    else None
                ),
                family_group_id=(
                    UUID(str(data["family_group_id"])) if data.get("family_group_id") else None
                ),
            )
            await commit_database()
            saved = True
            await show_today_from_callback(
                callback,
                state,
                telegram_service,
                restore_main_menu=True,
            )
            response = "Сохранено"
        except StaleStartDateError as error:
            await state.set_state(AddRegimen.summary)
            if isinstance(callback.message, Message):
                await callback.message.answer(f"Не удалось сохранить: {error}")
            response = "Проверьте данные"
        except Exception:
            if not saved:
                await state.set_state(AddRegimen.summary)
            raise
        finally:
            await callback.answer(response)

    @router.callback_query(F.data.startswith(f"{_PREFIX}:"))
    async def stale_callback(callback: CallbackQuery) -> None:
        await callback.answer("Эта кнопка устарела", show_alert=True)

    return router


async def _begin_wizard(message: Message, state: FSMContext, *, keep_target: bool = False) -> None:
    if keep_target:
        data = await state.get_data()
        await restart_wizard(state)
        await state.update_data(
            **{
                key: value
                for key, value in data.items()
                if key.startswith("target_") or key.startswith("family_")
            }
        )
    else:
        await restart_wizard(state)
    await message.answer("Введите название препарата:", reply_markup=_cancel_reply())


async def _ask_start_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddRegimen.start_date)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Когда начать? Введите дату ДД.ММ.ГГГГ или выберите:",
            reply_markup=_start_date_keyboard(),
        )
    await callback.answer()


async def _ask_meal_timing(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddRegimen.meal_timing)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Как принимать относительно еды?",
            reply_markup=_meal_timing_keyboard(),
        )
    await callback.answer()


async def _ask_reminder_target_callback(
    callback: CallbackQuery,
    state: FSMContext,
    medication_set_service: TelegramMedicationSetService,
) -> None:
    await state.set_state(AddRegimen.reminder_target)
    data = await state.get_data()
    sets = await medication_set_service.list(
        int(data.get("target_telegram_user_id", callback.from_user.id))
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Куда добавить препарат?",
            reply_markup=_reminder_target_keyboard(sets),
        )
    await callback.answer()


async def _ask_times_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(selected_times=[])
    await state.set_state(AddRegimen.times)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Выберите одно или несколько времён:",
            reply_markup=_times_keyboard(()),
        )
    await callback.answer()


async def _ask_ending_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddRegimen.ending)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Как завершить курс?", reply_markup=_ending_keyboard())
    await callback.answer()


async def _ask_ending_message(message: Message, state: FSMContext) -> None:
    await state.set_state(AddRegimen.ending)
    await message.answer("Как завершить курс?", reply_markup=_ending_keyboard())


async def _store_set_target(
    state: FSMContext,
    set_id: UUID | None,
    name: str,
    window_start: time,
    window_end: time,
) -> None:
    await state.update_data(
        reminder_mode="set",
        medication_set_id=str(set_id) if set_id is not None else None,
        medication_set_name=name,
        medication_set_window_start=window_start.strftime("%H:%M"),
        medication_set_window_end=window_end.strftime("%H:%M"),
        times=window_start.strftime("%H:%M"),
    )


async def _show_summary(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        command = command_from_state(await state.get_data())
    except WizardValidationError:
        await callback.answer("Данные мастера устарели", show_alert=True)
        return
    await state.set_state(AddRegimen.summary)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(format_summary(command), reply_markup=_summary_keyboard())
    await callback.answer()


def _common_time_from_callback(value: str) -> time:
    for item in COMMON_TIMES:
        if item.strftime("%H%M") == value:
            return item
    raise WizardValidationError("Некорректный вариант времени")


def _telegram_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user is not None else None


async def cancel_wizard(state: FSMContext) -> bool:
    had_state = await state.get_state() is not None
    await state.clear()
    return had_state


async def restart_wizard(state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddRegimen.name)
