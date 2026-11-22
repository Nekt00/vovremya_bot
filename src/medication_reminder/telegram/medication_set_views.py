from datetime import time
from html import escape
from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from medication_reminder.medication_sets.domain import MedicationSetDetails
from medication_reminder.medication_sets.presets import (
    MEDICATION_SET_EMOJI,
    MEDICATION_SET_PRESETS,
)
from medication_reminder.regimens.domain.regimen import Regimen
from medication_reminder.shared.dosage import format_dose
from medication_reminder.telegram.ui import (
    BACK,
    DANGER_STYLE,
    DELETE,
    DONE,
    MEDICATION,
    PRIMARY_STYLE,
    SETS,
    SETTINGS,
    SKIPPED,
    SUCCESS_STYLE,
)


def format_sets(items: list[MedicationSetDetails]) -> str:
    lines = [f"{SETS} <b>Наборы препаратов</b>"]
    if not items:
        return "\n".join([*lines, "", "Наборов пока нет."])
    for item in items:
        value = item.medication_set
        lines.extend(
            [
                "",
                f"<b>{escape(value.name)}</b> · "
                f"{value.window_start:%H:%M}–{value.window_end:%H:%M}",
            ]
        )
        for regimen in item.regimens:
            lines.append(
                f"• {escape(regimen.medication_name)} — "
                f"{escape(format_dose(regimen.dose_amount, regimen.dose_unit))}"
            )
    return "\n".join(lines)


def sets_keyboard(items: list[MedicationSetDetails]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{SETTINGS} {item.medication_set.name[:45]}",
                callback_data=f"ms:view:{item.medication_set.id}",
            )
        ]
        for item in items
    ]
    names = {item.medication_set.name.casefold() for item in items}
    for key, (name, _start, _end) in MEDICATION_SET_PRESETS.items():
        if name.casefold() not in names:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{MEDICATION_SET_EMOJI[key]} Создать «{name}»",
                        callback_data=f"ms:new:{key}",
                        style=PRIMARY_STYLE,
                    )
                ]
            )
    rows.append([InlineKeyboardButton(text="Сегодня", callback_data="nav:today")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def members_keyboard(
    regimens: list[Regimen],
    selected: frozenset[UUID],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=(f"{DONE} " if item.id in selected else "") + item.medication_name[:48],
                callback_data=f"ms:member:{item.id}",
                style=PRIMARY_STYLE if item.id in selected else None,
            )
        ]
        for item in regimens
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=f"{DONE} Сохранить набор",
                    callback_data="ms:save",
                    style=SUCCESS_STYLE,
                )
            ],
            [InlineKeyboardButton(text=f"{SKIPPED} Отмена", callback_data="ms:cancel")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_members_keyboard(
    regimens: list[Regimen],
    selected: frozenset[UUID],
    set_id: UUID,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=(f"{DONE} " if item.id in selected else "") + item.medication_name[:48],
                callback_data=f"ms:edit-member:{item.id}",
                style=PRIMARY_STYLE if item.id in selected else None,
            )
        ]
        for item in regimens
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=f"{DONE} Сохранить состав",
                    callback_data="ms:edit-members-save",
                    style=SUCCESS_STYLE,
                )
            ],
            [InlineKeyboardButton(text=f"{SKIPPED} Отмена", callback_data=f"ms:view:{set_id}")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_set(details: MedicationSetDetails) -> str:
    value = details.medication_set
    lines = [
        f"{SETS} <b>{escape(value.name)}</b>",
        f"Окно напоминаний: <b>{value.window_start:%H:%M}–{value.window_end:%H:%M}</b>",
        "",
        "Препараты:",
    ]
    lines.extend(
        f"• {escape(item.medication_name)} — "
        f"{escape(format_dose(item.dose_amount, item.dose_unit))}"
        for item in details.regimens
    )
    return "\n".join(lines)


def set_actions_keyboard(set_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{MEDICATION} Состав", callback_data=f"ms:edit-members:{set_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{DELETE} Удалить набор",
                    callback_data=f"ms:delete-ask:{set_id}",
                    style=DANGER_STYLE,
                )
            ],
            [InlineKeyboardButton(text=f"{BACK} К наборам", callback_data="ms:list")],
        ]
    )


def delete_confirmation_keyboard(set_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{DELETE} Удалить набор",
                    callback_data=f"ms:delete-yes:{set_id}",
                    style=DANGER_STYLE,
                )
            ],
            [InlineKeyboardButton(text=f"{BACK} Не удалять", callback_data=f"ms:view:{set_id}")],
        ]
    )


def parse_time(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("Time must use HH:MM format")
    hour, minute = map(int, parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Time is outside the daily range")
    return time(hour, minute)
