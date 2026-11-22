from html import escape
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from medication_reminder.regimens.domain.regimen import Regimen, RegimenStatus
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.shared.dosage import format_dose, meal_timing_label
from medication_reminder.telegram.callbacks import RegimenAction, RegimenCallback
from medication_reminder.telegram.regimen_service import RegimenDetails
from medication_reminder.telegram.ui import (
    BACK,
    DANGER_STYLE,
    DELETE,
    DONE,
    EDIT,
    MEDICATION,
    PAUSE,
    PRIMARY_STYLE,
    RESUME,
    STOP,
    SUCCESS_STYLE,
    form_icon,
)

_STATUS_LABEL = {
    RegimenStatus.ACTIVE: "активно",
    RegimenStatus.PAUSED: "на паузе",
    RegimenStatus.COMPLETED: "завершено",
}
_WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def format_regimen_list(regimens: list[Regimen]) -> tuple[str, InlineKeyboardMarkup | None]:
    if not regimens:
        return (
            f"{MEDICATION} <b>Курсы</b>\n\nКурсов пока нет.",
            InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Сегодня", callback_data="nav:today")]]
            ),
        )
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{form_icon(item.medication_form)} {item.medication_name} · "
                    f"{_STATUS_LABEL[item.status]}"
                )[:64],
                callback_data=RegimenCallback(item.id, RegimenAction.VIEW).encode(),
            )
        ]
        for item in regimens[:50]
    ]
    text = f"{MEDICATION} <b>Курсы</b>\n\nВыберите курс:"
    if len(regimens) > 50:
        text += "\n\nПоказаны последние 50 курсов."
    rows.append([InlineKeyboardButton(text="Сегодня", callback_data="nav:today")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def format_regimen_details(details: RegimenDetails) -> tuple[str, InlineKeyboardMarkup]:
    regimen = details.regimen
    ending = "без окончания"
    if regimen.total_intakes is not None:
        ending = f"{regimen.total_intakes} приёмов"
    elif regimen.end_date is not None:
        ending = f"до {regimen.end_date:%d.%m.%Y} включительно"
    schedule = _format_schedule(details)
    next_intake = _format_next_intake(details)
    text = (
        f"{form_icon(regimen.medication_form)} <b>{escape(regimen.medication_name)}</b>\n\n"
        f"Доза: <b>{escape(format_dose(regimen.dose_amount, regimen.dose_unit))}</b>\n"
        f"Приём пищи: <b>{meal_timing_label(regimen.meal_timing)}</b>\n"
        f"График: {escape(schedule)}\n"
        f"Следующий приём: <b>{escape(next_intake)}</b>\n"
        f"Начало: {regimen.start_date:%d.%m.%Y}\n"
        f"Курс: {ending}\n"
        f"Статус: <b>{_STATUS_LABEL[regimen.status]}</b>"
    )
    rows: list[list[InlineKeyboardButton]] = []
    if details.can_manage and regimen.status is RegimenStatus.ACTIVE:
        rows.append([_button(f"{EDIT} Изменить", regimen.id, RegimenAction.EDIT)])
        rows.append([_button(f"{PAUSE} Приостановить", regimen.id, RegimenAction.PAUSE)])
        rows.append([_button(f"{STOP} Завершить курс", regimen.id, RegimenAction.COMPLETE)])
    elif details.can_manage and regimen.status is RegimenStatus.PAUSED:
        rows.append([_button(f"{RESUME} Возобновить", regimen.id, RegimenAction.RESUME)])
        rows.append([_button(f"{STOP} Завершить курс", regimen.id, RegimenAction.COMPLETE)])
    if details.can_manage:
        rows.append([_button(f"{DELETE} Удалить", regimen.id, RegimenAction.DELETE)])
    elif details.family_assignment:
        text += "\n\n🔒 Изменять этот курс может только владелец семейной группы."
    rows.append(
        [
            InlineKeyboardButton(
                text=f"{BACK} Назад",
                callback_data=(
                    "family:home" if details.family_assignment and details.can_manage else "rg:list"
                ),
            )
        ]
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def completion_confirmation(details: RegimenDetails) -> tuple[str, InlineKeyboardMarkup]:
    regimen = details.regimen
    text = (
        f"Завершить курс <b>{escape(regimen.medication_name)}</b>?\n\n"
        "Все необработанные приёмы будут отменены. Это действие нельзя отменить."
    )
    return text, InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(f"{DONE} Завершить курс", regimen.id, RegimenAction.CONFIRM_COMPLETE)],
            [_button(f"{BACK} Назад", regimen.id, RegimenAction.VIEW)],
        ]
    )


def deletion_confirmation(details: RegimenDetails) -> tuple[str, InlineKeyboardMarkup]:
    regimen = details.regimen
    text = (
        f"Удалить курс <b>{escape(regimen.medication_name)}</b>?\n\n"
        "Будут удалены расписание и вся история этого курса. Действие нельзя отменить."
    )
    return text, InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(f"{DELETE} Удалить курс", regimen.id, RegimenAction.CONFIRM_DELETE)],
            [_button(f"{BACK} Назад", regimen.id, RegimenAction.VIEW)],
        ]
    )


def _format_schedule(details: RegimenDetails) -> str:
    if details.schedule is None:
        return "расписание недоступно"
    rule = details.schedule.rule
    if isinstance(rule, DailyScheduleRule):
        times = ", ".join(value.strftime("%H:%M") for value in rule.times)
        return f"ежедневно в {times}"
    if isinstance(rule, IntervalScheduleRule):
        times = ", ".join(value.strftime("%H:%M") for value in rule.times)
        return f"каждые {rule.every_days} дн. в {times}"
    if isinstance(rule, WeekdayScheduleRule):
        times = ", ".join(value.strftime("%H:%M") for value in rule.times)
        weekdays = ", ".join(_WEEKDAYS[value - 1] for value in sorted(rule.weekdays))
        return f"{weekdays} в {times}"
    if isinstance(rule, WeeklyScheduleRule):
        workdays = ", ".join(value.strftime("%H:%M") for value in rule.times_for_weekday(1))
        weekends = ", ".join(value.strftime("%H:%M") for value in rule.times_for_weekday(6))
        return f"будни в {workdays}; выходные в {weekends}"
    return "расписание недоступно"


def _format_next_intake(details: RegimenDetails) -> str:
    if details.regimen.status is RegimenStatus.PAUSED:
        return "курс приостановлен"
    if details.regimen.status is RegimenStatus.COMPLETED:
        return "курс завершён"
    if details.next_event is None:
        return "нет запланированных приёмов"
    local = details.next_event.scheduled_at.astimezone(ZoneInfo(details.next_event.timezone))
    return local.strftime("%d.%m.%Y в %H:%M")


def _button(text: str, regimen_id: UUID, action: RegimenAction) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=RegimenCallback(regimen_id, action).encode(),
        style=_button_style(action),
    )


def _button_style(action: RegimenAction) -> str | None:
    if action in {RegimenAction.DELETE, RegimenAction.CONFIRM_DELETE}:
        return DANGER_STYLE
    if action is RegimenAction.RESUME:
        return SUCCESS_STYLE
    if action in {RegimenAction.EDIT, RegimenAction.PAUSE}:
        return PRIMARY_STYLE
    return None
