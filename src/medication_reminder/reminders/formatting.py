from html import escape
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.reminders.repository import ClaimedReminder, ClaimedSetReminder
from medication_reminder.shared.dosage import format_dose, meal_timing_suffix
from medication_reminder.telegram.callbacks import (
    EventAction,
    EventCallback,
    SetTakeAllCallback,
)
from medication_reminder.telegram.ui import (
    DONE,
    SETS,
    SUCCESS_STYLE,
    form_icon,
)

_FORM_LABEL = {
    MedicationForm.TABLET: "таблетка",
    MedicationForm.CAPSULE: "капсула",
    MedicationForm.INJECTION: "укол",
    MedicationForm.DROPS: "капли",
    MedicationForm.OTHER: "препарат",
}


def format_reminder(reminder: ClaimedReminder) -> tuple[str, InlineKeyboardMarkup]:
    emoji = form_icon(reminder.medication_form)
    form_label = _FORM_LABEL[reminder.medication_form]
    local_time = reminder.scheduled_at.astimezone(ZoneInfo(reminder.timezone)).strftime("%H:%M")
    title = (
        "Пора сделать укол"
        if reminder.medication_form is MedicationForm.INJECTION
        else "Пора принять лекарство"
    )
    text = (
        f"{emoji} <b>{title}</b>\n\n"
        f"<b>{escape(reminder.medication_name)}</b>\n"
        f"{escape(format_dose(reminder.dose_amount, reminder.dose_unit))} · {form_label}"
        f"{meal_timing_suffix(reminder.meal_timing)}\n"
        f"По графику: <b>{local_time}</b>\n\n"
        "Отметьте приём — я сохраню фактическое время."
    )
    take_label = (
        "Укол сделан" if reminder.medication_form is MedicationForm.INJECTION else "Принять"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=take_label,
                    callback_data=EventCallback(reminder.event_id, EventAction.TAKE).encode(),
                    style=SUCCESS_STYLE,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отложить",
                    callback_data=EventCallback(reminder.event_id, EventAction.SNOOZE).encode(),
                ),
                InlineKeyboardButton(
                    text="Пропустить",
                    callback_data=EventCallback(reminder.event_id, EventAction.SKIP).encode(),
                ),
            ],
        ]
    )
    return text, keyboard


def format_set_reminder(reminder: ClaimedSetReminder) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        f"{SETS} <b>Пора принять набор «{escape(reminder.set_name)}»</b>",
        "",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for item in reminder.items:
        emoji = form_icon(item.medication_form)
        lines.append(
            f"{emoji} <b>{escape(item.medication_name)}</b> — "
            f"{escape(format_dose(item.dose_amount, item.dose_unit))}"
            f"{meal_timing_suffix(item.meal_timing)}"
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{emoji} {item.medication_name[:40]}",
                    callback_data=EventCallback(item.event_id, EventAction.VIEW).encode(),
                )
            ]
        )
    local_end = reminder.window_end.astimezone(ZoneInfo(reminder.timezone)).strftime("%H:%M")
    lines.extend(
        [
            "",
            f"Окно приёма — до <b>{local_end}</b>.",
            "Выберите препарат для действий или примите весь набор сразу.",
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"{DONE} Принять всё",
                callback_data=SetTakeAllCallback(reminder.set_id, reminder.local_date).encode(),
                style=SUCCESS_STYLE,
            )
        ]
    )
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)
