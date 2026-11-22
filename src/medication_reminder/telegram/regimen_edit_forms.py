from datetime import date, time
from decimal import Decimal
from typing import cast

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from medication_reminder.regimens.domain.regimen import MealTiming
from medication_reminder.schedules.domain.rules import ScheduleRule, WeeklyScheduleRule
from medication_reminder.shared.dosage import meal_timing_label
from medication_reminder.telegram.ui import (
    DONE,
    EDIT,
    MEDICATION,
    PRIMARY_STYLE,
    SKIPPED,
    SUCCESS_STYLE,
)
from medication_reminder.telegram.wizard_models import (
    COMMON_TIMES,
    MAX_TOTAL_INTAKES,
    QUICK_DOSE_AMOUNTS,
    ScheduleKind,
    WizardValidationError,
    build_rule,
    parse_dose_amount,
    parse_positive_int,
    parse_times,
)

PREFIX = "re"
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def revision_values(data: dict[str, object]) -> tuple[Decimal | None, ScheduleRule | None]:
    dose = parse_dose_amount(str(data["new_dose"])) if "new_dose" in data else None
    if "schedule_kind" not in data:
        return dose, None
    kind = ScheduleKind(str(data["schedule_kind"]))
    values = () if kind is ScheduleKind.WEEKLY else parse_times(str(data["times"]))
    rule = build_rule(
        kind,
        values,
        every_days=(int(str(data["every_days"])) if "every_days" in data else None),
        weekdays=frozenset(
            int(str(value)) for value in cast(list[object], data.get("weekdays", []))
        ),
        workday_times=(
            parse_times(str(data["workday_times"])) if kind is ScheduleKind.WEEKLY else ()
        ),
        weekend_times=(
            parse_times(str(data["weekend_times"])) if kind is ScheduleKind.WEEKLY else ()
        ),
    )
    return dose, rule


def ending_values(data: dict[str, object]) -> tuple[int | None, date | None]:
    remaining = (
        parse_positive_int(
            str(data["remaining_intakes"]),
            maximum=MAX_TOTAL_INTAKES,
            label="Количество приёмов",
        )
        if "remaining_intakes" in data
        else None
    )
    end_date = date.fromisoformat(str(data["end_date"])) if "end_date" in data else None
    return remaining, end_date


def meal_timing_value(data: dict[str, object]) -> MealTiming | None:
    value = data.get("new_meal_timing")
    return MealTiming(str(value)) if value is not None else None


def summary_text(data: dict[str, object]) -> str:
    dose, rule = revision_values(data)
    meal_timing = meal_timing_value(data)
    remaining_intakes, end_date = ending_values(data)
    lines = [f"{EDIT} <b>Изменение будущих приёмов</b>", ""]
    if dose is not None:
        lines.append(f"Новая дозировка: <b>{dose.normalize()}</b>")
    if meal_timing is not None:
        lines.append(f"Приём пищи: <b>{meal_timing_label(meal_timing)}</b>")
    if rule is not None:
        if isinstance(rule, WeeklyScheduleRule):
            workdays = ", ".join(value.strftime("%H:%M") for value in rule.times_for_weekday(1))
            weekends = ", ".join(value.strftime("%H:%M") for value in rule.times_for_weekday(6))
            label = f"будни {workdays}; выходные {weekends}"
        elif hasattr(rule, "every_days"):
            times = ", ".join(value.strftime("%H:%M") for value in rule.times)
            label = f"каждые {rule.every_days} дн."
        elif hasattr(rule, "weekdays"):
            times = ", ".join(value.strftime("%H:%M") for value in rule.times)
            label = ", ".join(WEEKDAYS[value - 1] for value in sorted(rule.weekdays))
        else:
            times = ", ".join(value.strftime("%H:%M") for value in rule.times)
            label = "ежедневно"
        suffix = "" if isinstance(rule, WeeklyScheduleRule) else f", {times}"
        lines.append(f"Новый график: <b>{label}{suffix}</b>")
    if remaining_intakes is not None:
        lines.append(f"Осталось приёмов: <b>{remaining_intakes}</b>")
    if end_date is not None:
        lines.append(f"Новая дата окончания: <b>{end_date:%d.%m.%Y}</b>")
    lines.extend(["", "Изменения затронут только будущие запланированные приёмы."])
    return "\n".join(lines)


def mode_keyboard() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [(f"{MEDICATION} Дозировку", f"{PREFIX}:mode:dose")],
            [("🍽 Связь с едой", f"{PREFIX}:mode:meal")],
            [("🗓 График", f"{PREFIX}:mode:schedule")],
            [("🔢 Длительность курса", f"{PREFIX}:mode:duration")],
            [(f"{EDIT} Дозу и график", f"{PREFIX}:mode:both")],
        ]
    )


def meal_timing_keyboard() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [("До еды", f"{PREFIX}:meal:before"), ("Во время", f"{PREFIX}:meal:during")],
            [("После еды", f"{PREFIX}:meal:after"), ("Неважно", f"{PREFIX}:meal:independent")],
        ]
    )


def duration_kind_keyboard() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [("Оставшееся количество", f"{PREFIX}:duration:count")],
            [("Дата окончания", f"{PREFIX}:duration:date")],
        ]
    )


def dose_keyboard() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [(value, f"{PREFIX}:dose:{value}") for value in QUICK_DOSE_AMOUNTS],
            [(f"{EDIT} Ввести свою", f"{PREFIX}:dose:custom")],
        ]
    )


def schedule_keyboard() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [("Ежедневно", f"{PREFIX}:kind:d")],
            [("Каждые N дней", f"{PREFIX}:kind:i")],
            [("По дням недели", f"{PREFIX}:kind:w")],
            [("Будни / выходные — разное время", f"{PREFIX}:kind:x")],
        ]
    )


def weekdays_keyboard(selected: frozenset[int]) -> InlineKeyboardMarkup:
    buttons = [
        ((f"{DONE} " if value in selected else "") + label, f"{PREFIX}:weekday:{value}")
        for value, label in enumerate(WEEKDAYS, start=1)
    ]
    return keyboard([buttons[:4], buttons[4:], [("Готово", f"{PREFIX}:weekday:done")]])


def times_keyboard(selected: tuple[time, ...]) -> InlineKeyboardMarkup:
    buttons = [
        (
            (f"{DONE} " if value in selected else "") + value.strftime("%H:%M"),
            f"{PREFIX}:time:{value:%H%M}",
        )
        for value in COMMON_TIMES
    ]
    return keyboard(
        [
            buttons[:4],
            buttons[4:],
            [("Готово", f"{PREFIX}:time:done")],
            [(f"{EDIT} Ввести своё", f"{PREFIX}:time:custom")],
        ]
    )


def summary_keyboard() -> InlineKeyboardMarkup:
    return keyboard([[(f"{DONE} Применить", f"{PREFIX}:save")]], cancel=True)


def keyboard(
    rows: list[list[tuple[str, str]]],
    *,
    cancel: bool = True,
) -> InlineKeyboardMarkup:
    result = [
        [
            InlineKeyboardButton(
                text=text,
                callback_data=data,
                style=(
                    SUCCESS_STYLE
                    if data == f"{PREFIX}:save"
                    else PRIMARY_STYLE
                    if text.startswith(DONE)
                    else None
                ),
            )
            for text, data in row
        ]
        for row in rows
    ]
    if cancel:
        result.append(
            [InlineKeyboardButton(text=f"{SKIPPED} Отмена", callback_data=f"{PREFIX}:cancel")]
        )
    return InlineKeyboardMarkup(inline_keyboard=result)


def selected_times(data: dict[str, object]) -> tuple[time, ...]:
    values = cast(list[object], data.get("selected_times", []))
    return parse_times(", ".join(str(value) for value in values)) if values else ()


def common_time(value: str) -> time:
    for item in COMMON_TIMES:
        if item.strftime("%H%M") == value:
            return item
    raise WizardValidationError("Некорректное время")
