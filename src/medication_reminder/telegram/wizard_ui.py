from datetime import time

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from medication_reminder.medication_sets.domain import MedicationSetDetails
from medication_reminder.medication_sets.presets import (
    MEDICATION_SET_EMOJI,
    MEDICATION_SET_PRESETS,
)
from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.telegram.ui import (
    CLOCK,
    DONE,
    EDIT,
    PRIMARY_STYLE,
    SKIPPED,
    SUCCESS_STYLE,
    form_icon,
)
from medication_reminder.telegram.wizard_models import COMMON_TIMES, QUICK_DOSE_AMOUNTS

CANCEL_BUTTON = f"{SKIPPED} Отмена"
PREFIX = "w"
FORM_LABELS = {
    MedicationForm.TABLET: f"{form_icon(MedicationForm.TABLET)} Таблетка",
    MedicationForm.CAPSULE: f"{form_icon(MedicationForm.CAPSULE)} Капсула",
    MedicationForm.INJECTION: f"{form_icon(MedicationForm.INJECTION)} Укол",
    MedicationForm.DROPS: f"{form_icon(MedicationForm.DROPS)} Капли",
    MedicationForm.OTHER: f"{form_icon(MedicationForm.OTHER)} Другое",
}
UNIT_PRESETS = {
    MedicationForm.TABLET: ("таблетка",),
    MedicationForm.CAPSULE: ("капсула",),
    MedicationForm.INJECTION: ("мл", "мг"),
    MedicationForm.DROPS: ("капля", "мл"),
    MedicationForm.OTHER: ("мг", "мл"),
}
SET_PRESETS = MEDICATION_SET_PRESETS
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def form_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{PREFIX}:form:{form.value}")]
        for form, label in FORM_LABELS.items()
    ]
    return with_cancel(rows)


def dose_amount_keyboard() -> InlineKeyboardMarkup:
    quick_buttons = [
        InlineKeyboardButton(text=value, callback_data=f"{PREFIX}:dose:{value}")
        for value in QUICK_DOSE_AMOUNTS
    ]
    return with_cancel(
        [
            quick_buttons,
            [
                InlineKeyboardButton(
                    text=f"{EDIT} Ввести своё", callback_data=f"{PREFIX}:dose:custom"
                )
            ],
        ]
    )


def unit_keyboard(form: MedicationForm) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=value, callback_data=f"{PREFIX}:unit:{index}")]
        for index, value in enumerate(UNIT_PRESETS[form])
    ]
    rows.append([InlineKeyboardButton(text="Другая", callback_data=f"{PREFIX}:unit:other")])
    return with_cancel(rows)


def start_date_keyboard() -> InlineKeyboardMarkup:
    return with_cancel(
        [
            [
                InlineKeyboardButton(text="Сегодня", callback_data=f"{PREFIX}:start:today"),
                InlineKeyboardButton(text="Завтра", callback_data=f"{PREFIX}:start:tomorrow"),
            ]
        ]
    )


def meal_timing_keyboard() -> InlineKeyboardMarkup:
    return with_cancel(
        [
            [
                InlineKeyboardButton(text="До еды", callback_data=f"{PREFIX}:meal:before"),
                InlineKeyboardButton(text="Во время еды", callback_data=f"{PREFIX}:meal:during"),
            ],
            [
                InlineKeyboardButton(text="После еды", callback_data=f"{PREFIX}:meal:after"),
                InlineKeyboardButton(text="Неважно", callback_data=f"{PREFIX}:meal:independent"),
            ],
        ]
    )


def reminder_target_keyboard(items: list[MedicationSetDetails]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key, (name, default_start, default_end) in SET_PRESETS.items():
        existing = next(
            (
                item.medication_set
                for item in items
                if item.medication_set.name.casefold() == name.casefold()
            ),
            None,
        )
        start = existing.window_start if existing is not None else default_start
        end = existing.window_end if existing is not None else default_end
        callback_value = str(existing.id) if existing is not None else key
        emoji = MEDICATION_SET_EMOJI[key]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{emoji} {name} · {start:%H:%M}–{end:%H:%M}",
                    callback_data=f"{PREFIX}:target:{callback_value}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"{CLOCK} Отдельное точное время",
                callback_data=f"{PREFIX}:target:exact",
            )
        ]
    )
    return with_cancel(rows)


def schedule_keyboard(*, allow_weekly: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Ежедневно", callback_data=f"{PREFIX}:schedule:d")],
        [InlineKeyboardButton(text="Каждые N дней", callback_data=f"{PREFIX}:schedule:i")],
        [InlineKeyboardButton(text="По дням недели", callback_data=f"{PREFIX}:schedule:w")],
    ]
    if allow_weekly:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Будни / выходные — разное время",
                    callback_data=f"{PREFIX}:schedule:x",
                )
            ]
        )
    return with_cancel(rows)


def weekdays_keyboard(selected: frozenset[int]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=(f"{DONE} " if index in selected else "") + label,
            callback_data=f"{PREFIX}:weekday:{index}",
            style=PRIMARY_STYLE if index in selected else None,
        )
        for index, label in enumerate(WEEKDAYS, start=1)
    ]
    return with_cancel(
        [
            buttons[:4],
            buttons[4:],
            [InlineKeyboardButton(text="Готово", callback_data=f"{PREFIX}:weekday:done")],
        ]
    )


def times_keyboard(selected: tuple[time, ...]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=(f"{DONE} " if value in selected else "") + value.strftime("%H:%M"),
            callback_data=f"{PREFIX}:time:{value:%H%M}",
            style=PRIMARY_STYLE if value in selected else None,
        )
        for value in COMMON_TIMES
    ]
    return with_cancel(
        [
            buttons[:4],
            buttons[4:],
            [InlineKeyboardButton(text="Готово", callback_data=f"{PREFIX}:time:done")],
            [
                InlineKeyboardButton(
                    text=f"{EDIT} Ввести своё", callback_data=f"{PREFIX}:time:custom"
                )
            ],
        ]
    )


def ending_keyboard() -> InlineKeyboardMarkup:
    return with_cancel(
        [
            [
                InlineKeyboardButton(
                    text="По количеству приёмов", callback_data=f"{PREFIX}:ending:c"
                )
            ],
            [InlineKeyboardButton(text="По дате", callback_data=f"{PREFIX}:ending:e")],
            [InlineKeyboardButton(text="Без окончания", callback_data=f"{PREFIX}:ending:o")],
        ]
    )


def summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{DONE} Сохранить",
                    callback_data=f"{PREFIX}:save",
                    style=SUCCESS_STYLE,
                )
            ],
            [InlineKeyboardButton(text=f"{EDIT} Начать заново", callback_data=f"{PREFIX}:restart")],
            [InlineKeyboardButton(text=CANCEL_BUTTON, callback_data=f"{PREFIX}:cancel")],
        ]
    )


def with_cancel(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *rows,
            [InlineKeyboardButton(text=CANCEL_BUTTON, callback_data=f"{PREFIX}:cancel")],
        ]
    )


def cancel_reply() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
