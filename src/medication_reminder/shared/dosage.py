from decimal import Decimal

from medication_reminder.regimens.domain.regimen import MealTiming

_FORMS: dict[str, tuple[str, str, str]] = {
    "таблетка": ("таблетка", "таблетки", "таблеток"),
    "таблетки": ("таблетка", "таблетки", "таблеток"),
    "таблеток": ("таблетка", "таблетки", "таблеток"),
    "капсула": ("капсула", "капсулы", "капсул"),
    "капсулы": ("капсула", "капсулы", "капсул"),
    "капсул": ("капсула", "капсулы", "капсул"),
    "капля": ("капля", "капли", "капель"),
    "капли": ("капля", "капли", "капель"),
    "капель": ("капля", "капли", "капель"),
}


def format_dose(amount: Decimal, unit: str) -> str:
    formatted_amount = format_decimal(amount)
    forms = _FORMS.get(unit.strip().casefold())
    if forms is None:
        return f"{formatted_amount} {unit}"
    return f"{formatted_amount} {_select_form(amount, forms)}"


def format_decimal(value: Decimal) -> str:
    if value == value.to_integral():
        return str(int(value))
    return format(value, "f").rstrip("0").rstrip(".")


def meal_timing_label(value: MealTiming) -> str:
    return {
        MealTiming.INDEPENDENT: "не зависит от еды",
        MealTiming.BEFORE: "до еды",
        MealTiming.DURING: "во время еды",
        MealTiming.AFTER: "после еды",
    }[value]


def meal_timing_suffix(value: MealTiming) -> str:
    if value is MealTiming.INDEPENDENT:
        return ""
    return f" · {meal_timing_label(value)}"


def _select_form(amount: Decimal, forms: tuple[str, str, str]) -> str:
    if amount != amount.to_integral():
        return forms[1]
    value = abs(int(amount))
    if value % 100 in range(11, 15):
        return forms[2]
    if value % 10 == 1:
        return forms[0]
    if value % 10 in range(2, 5):
        return forms[1]
    return forms[2]
