from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from html import escape
from math import ceil
from re import fullmatch
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from medication_reminder.regimens.domain.regimen import (
    MAX_DOSE_UNIT_LENGTH,
    MAX_MEDICATION_NAME_LENGTH,
    MealTiming,
    MedicationForm,
)
from medication_reminder.schedules.domain.generator import MAX_SCANNED_DAYS
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    ScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.shared.dosage import format_dose

MAX_INTERVAL_DAYS = 365
MAX_TOTAL_INTAKES = 10_000
OPEN_ENDED_HORIZON_DAYS = 90
QUICK_DOSE_AMOUNTS: tuple[str, ...] = ("0.5", "1", "2", "5")
COMMON_TIMES: tuple[time, ...] = (
    time(6),
    time(8),
    time(9),
    time(12),
    time(18),
    time(21),
    time(22),
)
_DECIMAL_PATTERN = r"\d{1,9}(?:[.,]\d{1,6})?"
_TIME_PATTERN = r"(?:[01]\d|2[0-3]):[0-5]\d"


class WizardValidationError(ValueError):
    pass


class ScheduleKind(StrEnum):
    DAILY = "d"
    INTERVAL = "i"
    WEEKDAYS = "w"
    WEEKLY = "x"


class EndingKind(StrEnum):
    TOTAL_INTAKES = "c"
    END_DATE = "e"
    OPEN_ENDED = "o"


@dataclass(frozen=True, slots=True)
class MedicationSetTarget:
    set_id: UUID | None
    name: str
    window_start: time
    window_end: time

    def __post_init__(self) -> None:
        normalized = " ".join(self.name.split())
        if not normalized or len(normalized) > 64:
            raise WizardValidationError("Название набора должно содержать от 1 до 64 символов")
        if self.window_start >= self.window_end:
            raise WizardValidationError("Конец окна набора должен быть позже начала")
        object.__setattr__(self, "name", normalized)


@dataclass(frozen=True, slots=True)
class NewRegimenCommand:
    medication_name: str
    medication_form: MedicationForm
    dose_amount: Decimal
    dose_unit: str
    start_date: date
    rule: ScheduleRule
    total_intakes: int | None
    end_date: date | None
    medication_set: MedicationSetTarget | None = None
    meal_timing: MealTiming = MealTiming.INDEPENDENT


def parse_medication_name(value: str) -> str:
    return _parse_text(value, "Название", MAX_MEDICATION_NAME_LENGTH)


def parse_dose_unit(value: str) -> str:
    return _parse_text(value, "Единица дозы", MAX_DOSE_UNIT_LENGTH)


def parse_dose_amount(value: str) -> Decimal:
    normalized = value.strip()
    if fullmatch(_DECIMAL_PATTERN, normalized) is None:
        raise WizardValidationError("Введите положительное число, например 1 или 2,5")
    try:
        result = Decimal(normalized.replace(",", "."))
    except InvalidOperation as error:
        raise WizardValidationError("Некорректная дозировка") from error
    if not result.is_finite() or result <= 0:
        raise WizardValidationError("Дозировка должна быть больше нуля")
    return result


def parse_quick_dose(value: str) -> Decimal:
    if value not in QUICK_DOSE_AMOUNTS:
        raise WizardValidationError("Некорректный вариант количества")
    return parse_dose_amount(value)


def parse_local_date(value: str) -> date:
    normalized = value.strip()
    if fullmatch(r"\d{2}\.\d{2}\.\d{4}", normalized) is None:
        raise WizardValidationError("Введите дату в формате ДД.ММ.ГГГГ")
    try:
        return datetime.strptime(normalized, "%d.%m.%Y").date()
    except ValueError as error:
        raise WizardValidationError("Введите дату в формате ДД.ММ.ГГГГ") from error


def require_not_past(value: date, *, now: datetime, timezone: str) -> date:
    if value < now.astimezone(ZoneInfo(timezone)).date():
        raise WizardValidationError("Дата начала не может быть в прошлом")
    return value


def parse_times(value: str) -> tuple[time, ...]:
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(fullmatch(_TIME_PATTERN, part) is None for part in parts):
        raise WizardValidationError("Введите время как 09:00 или 09:00, 21:00")
    if len(parts) > 24:
        raise WizardValidationError("Можно указать не более 24 времён")
    parsed = tuple(time.fromisoformat(part) for part in parts)
    if len(set(parsed)) != len(parsed):
        raise WizardValidationError("Время не должно повторяться")
    return tuple(sorted(parsed))


def toggle_time(selected: tuple[time, ...], value: time) -> tuple[time, ...]:
    if value not in COMMON_TIMES:
        raise WizardValidationError("Некорректный вариант времени")
    values = set(selected)
    if value in values:
        values.remove(value)
    else:
        values.add(value)
    return tuple(sorted(values))


def parse_positive_int(value: str, *, maximum: int, label: str) -> int:
    normalized = value.strip()
    if not normalized.isascii() or not normalized.isdecimal():
        raise WizardValidationError(f"{label} должно быть целым положительным числом")
    result = int(normalized)
    if not 1 <= result <= maximum:
        raise WizardValidationError(f"{label} должно быть от 1 до {maximum}")
    return result


def build_rule(
    kind: ScheduleKind,
    times: tuple[time, ...],
    *,
    every_days: int | None = None,
    weekdays: frozenset[int] = frozenset(),
    workday_times: tuple[time, ...] = (),
    weekend_times: tuple[time, ...] = (),
) -> ScheduleRule:
    if kind is ScheduleKind.DAILY:
        return DailyScheduleRule(times)
    if kind is ScheduleKind.INTERVAL:
        if every_days is None:
            raise WizardValidationError("Не указан интервал")
        return IntervalScheduleRule(every_days, times)
    if kind is ScheduleKind.WEEKDAYS:
        if not weekdays:
            raise WizardValidationError("Выберите хотя бы один день недели")
        return WeekdayScheduleRule(weekdays, times)
    if not workday_times or not weekend_times:
        raise WizardValidationError("Укажите время для будней и выходных")
    return WeeklyScheduleRule(
        tuple(
            [(weekday, workday_times) for weekday in range(1, 6)]
            + [(weekday, weekend_times) for weekday in range(6, 8)]
        )
    )


def toggle_weekday(selected: frozenset[int], weekday: int) -> frozenset[int]:
    if weekday not in range(1, 8):
        raise WizardValidationError("Некорректный день недели")
    return selected ^ {weekday}


def command_from_state(data: dict[str, Any]) -> NewRegimenCommand:
    try:
        medication_set = _medication_set_from_state(data)
        kind = ScheduleKind(str(data["schedule_kind"]))
        times = () if kind is ScheduleKind.WEEKLY else parse_times(str(data["times"]))
        start_date = parse_local_date(str(data["start_date"]))
        ending = EndingKind(str(data["ending_kind"]))
        rule = build_rule(
            kind,
            times,
            every_days=(
                parse_positive_int(
                    str(data["every_days"]), maximum=MAX_INTERVAL_DAYS, label="Интервал"
                )
                if kind is ScheduleKind.INTERVAL
                else None
            ),
            weekdays=frozenset(int(value) for value in data.get("weekdays", [])),
            workday_times=(
                parse_times(str(data["workday_times"])) if kind is ScheduleKind.WEEKLY else ()
            ),
            weekend_times=(
                parse_times(str(data["weekend_times"])) if kind is ScheduleKind.WEEKLY else ()
            ),
        )
        total_intakes = (
            parse_positive_int(
                str(data["total_intakes"]),
                maximum=MAX_TOTAL_INTAKES,
                label="Количество приёмов",
            )
            if ending is EndingKind.TOTAL_INTAKES
            else None
        )
        end_date = (
            parse_local_date(str(data["end_date"])) if ending is EndingKind.END_DATE else None
        )
        if end_date is not None and end_date < start_date:
            raise WizardValidationError("Дата окончания не может быть раньше даты начала")
        command = NewRegimenCommand(
            medication_name=parse_medication_name(str(data["medication_name"])),
            medication_form=MedicationForm(str(data["medication_form"])),
            dose_amount=parse_dose_amount(str(data["dose_amount"])),
            dose_unit=parse_dose_unit(str(data["dose_unit"])),
            start_date=start_date,
            rule=rule,
            total_intakes=total_intakes,
            end_date=end_date,
            medication_set=medication_set,
            meal_timing=MealTiming(str(data.get("meal_timing", "independent"))),
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, WizardValidationError):
            raise
        raise WizardValidationError("Данные мастера неполны или устарели") from error
    validate_generation_horizon(command)
    return command


def required_horizon_days(command: NewRegimenCommand) -> int:
    if command.total_intakes is None:
        return OPEN_ENDED_HORIZON_DAYS
    if isinstance(command.rule, WeeklyScheduleRule):
        intakes_per_week = sum(len(times) for _, times in command.rule.times_by_weekday)
        return ceil(command.total_intakes / intakes_per_week) * 7 + 6
    days_with_events = ceil(command.total_intakes / len(command.rule.times))
    if isinstance(command.rule, DailyScheduleRule):
        return days_with_events
    if isinstance(command.rule, IntervalScheduleRule):
        return (days_with_events - 1) * command.rule.every_days + 1
    return days_with_events * 7 + 6


def validate_generation_horizon(command: NewRegimenCommand) -> None:
    if (
        command.end_date is not None
        and (command.end_date - command.start_date).days + 1 > MAX_SCANNED_DAYS
    ):
        raise WizardValidationError(f"Курс по дате не может быть длиннее {MAX_SCANNED_DAYS} дней")
    if command.total_intakes is not None and required_horizon_days(command) > MAX_SCANNED_DAYS:
        raise WizardValidationError(
            "Этот курс слишком длинный для одного расписания; уменьшите интервал или число приёмов"
        )


def format_summary(command: NewRegimenCommand) -> str:
    form_label = {
        MedicationForm.TABLET: "таблетка",
        MedicationForm.CAPSULE: "капсула",
        MedicationForm.INJECTION: "укол",
        MedicationForm.DROPS: "капли",
        MedicationForm.OTHER: "другое",
    }[command.medication_form]
    if isinstance(command.rule, DailyScheduleRule):
        times = ", ".join(value.strftime("%H:%M") for value in command.rule.times)
        schedule = "ежедневно" if command.medication_set is not None else f"ежедневно в {times}"
    elif isinstance(command.rule, IntervalScheduleRule):
        times = ", ".join(value.strftime("%H:%M") for value in command.rule.times)
        schedule = (
            f"каждые {command.rule.every_days} дн."
            if command.medication_set is not None
            else f"каждые {command.rule.every_days} дн., в {times}"
        )
    elif isinstance(command.rule, WeekdayScheduleRule):
        times = ", ".join(value.strftime("%H:%M") for value in command.rule.times)
        labels = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
        selected = ", ".join(labels[value - 1] for value in sorted(command.rule.weekdays))
        schedule = selected if command.medication_set is not None else f"{selected}, в {times}"
    else:
        workdays = ", ".join(value.strftime("%H:%M") for value in command.rule.times_for_weekday(1))
        weekends = ", ".join(value.strftime("%H:%M") for value in command.rule.times_for_weekday(6))
        schedule = f"будни в {workdays}; выходные в {weekends}"
    if command.total_intakes is not None:
        ending = f"{command.total_intakes} приёмов"
    elif command.end_date is not None:
        ending = f"до {command.end_date:%d.%m.%Y} включительно"
    else:
        ending = "без даты окончания"
    dose = format_dose(command.dose_amount, command.dose_unit)
    reminder = (
        f"\nНабор: <b>{escape(command.medication_set.name)}</b> · "
        f"{command.medication_set.window_start:%H:%M}–"
        f"{command.medication_set.window_end:%H:%M}"
        if command.medication_set is not None
        else ""
    )
    return (
        "<b>Проверьте курс</b>\n\n"
        f"Название: <b>{escape(command.medication_name)}</b>\n"
        f"Форма: {form_label}\n"
        f"Доза: {escape(dose)}\n"
        f"Приём пищи: {_meal_timing_label(command.meal_timing)}\n"
        f"Начало: {command.start_date:%d.%m.%Y}\n"
        f"График: {schedule}{reminder}\n"
        f"Окончание: {ending}"
    )


def _medication_set_from_state(data: dict[str, Any]) -> MedicationSetTarget | None:
    if data.get("reminder_mode") != "set":
        return None
    try:
        set_id_value = data.get("medication_set_id")
        return MedicationSetTarget(
            set_id=UUID(str(set_id_value)) if set_id_value else None,
            name=str(data["medication_set_name"]),
            window_start=parse_times(str(data["medication_set_window_start"]))[0],
            window_end=parse_times(str(data["medication_set_window_end"]))[0],
        )
    except (KeyError, ValueError) as error:
        if isinstance(error, WizardValidationError):
            raise
        raise WizardValidationError("Данные выбранного набора устарели") from error


def _meal_timing_label(value: MealTiming) -> str:
    return {
        MealTiming.INDEPENDENT: "неважно",
        MealTiming.BEFORE: "до еды",
        MealTiming.DURING: "во время еды",
        MealTiming.AFTER: "после еды",
    }[value]


def _parse_text(value: str, label: str, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise WizardValidationError(f"{label} не может быть пустым")
    if len(normalized) > maximum:
        raise WizardValidationError(f"{label}: не более {maximum} символов")
    if any(ord(character) < 32 for character in normalized):
        raise WizardValidationError(f"{label} содержит недопустимые символы")
    return normalized


def _format_decimal(value: Decimal) -> str:
    if value == value.to_integral():
        return str(int(value))
    return format(value, "f").rstrip("0").rstrip(".")
