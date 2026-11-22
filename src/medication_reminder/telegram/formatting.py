from html import escape
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.application.windows import UpcomingIntake
from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventStatus
from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.shared.dosage import format_dose, meal_timing_suffix
from medication_reminder.telegram.callbacks import EventAction, EventCallback, SnoozeCallback
from medication_reminder.telegram.ui import (
    CALENDAR,
    DONE,
    HISTORY,
    PENDING,
    PRIMARY_STYLE,
    SKIPPED,
    SNOOZE,
    SUCCESS_STYLE,
    form_icon,
)

_STATUS_LABEL = {
    IntakeEventStatus.SCHEDULED: "запланировано",
    IntakeEventStatus.DUE: "пора принять",
    IntakeEventStatus.SNOOZED: "отложено",
    IntakeEventStatus.TAKEN: "выполнено ✅",
    IntakeEventStatus.SKIPPED: "пропущено",
    IntakeEventStatus.MISSED: "не выполнено",
    IntakeEventStatus.CANCELLED: "отменено",
}
_WEEKDAY_LABELS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
_HISTORY_LIMIT = 50
_HISTORY_TEXT_LIMIT = 3_800


def allowed_actions(status: IntakeEventStatus) -> tuple[EventAction, ...]:
    if status is IntakeEventStatus.DUE:
        return (EventAction.TAKE, EventAction.SNOOZE, EventAction.SKIP)
    if status in {IntakeEventStatus.SCHEDULED, IntakeEventStatus.SNOOZED}:
        return (EventAction.TAKE, EventAction.SKIP)
    return ()


def format_today(
    details: list[IntakeEventDetails],
    timezone: str,
    *,
    upcoming: UpcomingIntake | None = None,
    window_label: str | None = None,
) -> tuple[str, InlineKeyboardMarkup | None]:
    next_text = (
        f"Следующий приём сегодня: <b>{upcoming.at.astimezone(ZoneInfo(timezone)):%H:%M}</b>"
        f" · {escape(upcoming.label)}\nНапомню в запланированное время."
        if upcoming is not None
        else "Следующих приёмов на сегодня нет."
    )
    visible = [item for item in details if item.event.status is not IntakeEventStatus.CANCELLED]
    if not visible:
        empty_text = next_text if upcoming is not None else "На сегодня приёмов нет."
        return (
            f"{CALENDAR} <b>Сегодня · Текущее окно</b>\n\n"
            f"{empty_text}"
        ), InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отметить приём вручную", callback_data="intakes:edit")],
            ]
        )

    zone = ZoneInfo(timezone)
    taken = sum(item.event.status is IntakeEventStatus.TAKEN for item in visible)
    not_completed = sum(
        item.event.status in {IntakeEventStatus.SKIPPED, IntakeEventStatus.MISSED}
        for item in visible
    )
    pending = len(visible) - taken - not_completed
    lines = [
        f"{CALENDAR} <b>Сегодня · Текущее окно</b>",
        escape(window_label) if window_label else "",
        "",
        f"{DONE} Выполнено: <b>{taken}</b>   {PENDING} Ожидает: <b>{pending}</b>",
        f"{SKIPPED} Не выполнено: <b>{not_completed}</b>",
        "",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for item in visible:
        event = item.event
        lines.append(
            f"{form_icon(item.medication_form)} <b>{escape(item.medication_name)}</b>\n"
            f"{escape(format_dose(item.dose_amount, item.dose_unit))}"
            f"{meal_timing_suffix(item.meal_timing)} · {_event_time_label(event, zone)} · "
            f"{_STATUS_LABEL[event.status]}\n"
        )
        if allowed_actions(event.status):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{form_icon(item.medication_form)} {item.medication_name[:40]}",
                        callback_data=EventCallback(event.id, EventAction.VIEW).encode(),
                    )
                ]
            )
    lines.extend(["", next_text])
    rows.append(
        [InlineKeyboardButton(text="Отметить приём вручную", callback_data="intakes:edit")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    return "\n".join(lines), markup


def format_intake_detail(
    item: IntakeEventDetails, timezone: str
) -> tuple[str, InlineKeyboardMarkup]:
    event = item.event
    text = (
        f"{form_icon(item.medication_form)} <b>{escape(item.medication_name)}</b>\n\n"
        f"{escape(format_dose(item.dose_amount, item.dose_unit))}"
        f"{meal_timing_suffix(item.meal_timing)}\n"
        f"{_event_time_label(event, ZoneInfo(timezone))} · {_STATUS_LABEL[event.status]}\n\n"
        "Действие относится только к этому препарату."
    )
    rows = [
        [
            InlineKeyboardButton(
                text=_action_label(action, item.medication_form),
                callback_data=EventCallback(event.id, action).encode(),
                style=_action_style(action),
            )
        ]
        for action in allowed_actions(event.status)
    ]
    rows.append([InlineKeyboardButton(text="Назад · Сегодня", callback_data="nav:today")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def format_intake_editor(
    details: list[IntakeEventDetails], timezone: str
) -> tuple[str, InlineKeyboardMarkup]:
    zone = ZoneInfo(timezone)
    rows: list[list[InlineKeyboardButton]] = []
    for item in sorted(details, key=lambda item: item.event.scheduled_at):
        event = item.event
        if event.status is IntakeEventStatus.CANCELLED:
            continue
        taken = event.status is IntakeEventStatus.TAKEN
        local_time = event.scheduled_at.astimezone(zone).strftime("%H:%M")
        label = f"{'✅' if taken else '⬜'} {local_time} · {item.medication_name[:45]}"
        action = EventAction.UNDO if taken else EventAction.TAKE
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"edit:{EventCallback(event.id, action).encode()}",
                    style=SUCCESS_STYLE if taken else None,
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Готово · Сегодня", callback_data="nav:today")])
    text = (
        "<b>Отметить приём · Сегодня</b>\n\n"
        "✅ — принято, ⬜ — ожидает.\n"
        "Нажмите на препарат, чтобы изменить статус. Повторное нажатие вернёт его обратно.\n\n"
        "После отмены напоминание придёт в запланированное время своего набора."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def format_history(
    details: list[IntakeEventDetails],
    timezone: str,
    *,
    days: int,
) -> tuple[str, InlineKeyboardMarkup]:
    visible = [item for item in details if item.event.status is not IntakeEventStatus.CANCELLED]
    taken = sum(item.event.status is IntakeEventStatus.TAKEN for item in visible)
    skipped = sum(
        item.event.status in {IntakeEventStatus.SKIPPED, IntakeEventStatus.MISSED}
        for item in visible
    )
    pending = len(visible) - taken - skipped
    lines = [
        f"{HISTORY} <b>История за {days} дней</b>",
        "",
        f"{DONE} Выполнено: <b>{taken}</b> · {SKIPPED} Пропущено: <b>{skipped}</b> · "
        f"{PENDING} Ожидает: <b>{pending}</b>",
    ]
    resolved = taken + skipped
    if resolved:
        lines.append(f"Соблюдение графика: <b>{round(taken / resolved * 100)}%</b>")
    if not visible:
        lines.extend(["", "За выбранный период приёмов нет."])
        return "\n".join(lines), _history_keyboard(days)

    zone = ZoneInfo(timezone)
    current_date = None
    displayed = 0
    shown = sorted(visible, key=lambda item: item.event.scheduled_at, reverse=True)[:_HISTORY_LIMIT]
    for item in shown:
        event = item.event
        local = (event.taken_at or event.scheduled_at).astimezone(zone)
        additions: list[str] = []
        if local.date() != current_date:
            additions.extend(
                [
                    "",
                    f"<b>{local:%d.%m.%Y} · {_WEEKDAY_LABELS[local.isoweekday() - 1]}</b>",
                ]
            )
        additions.append(
            f"{_history_status_icon(item.event.status)} "
            f"{form_icon(item.medication_form)} {escape(item.medication_name)} — "
            f"{escape(format_dose(item.dose_amount, item.dose_unit))}"
            f"{meal_timing_suffix(item.meal_timing)} · {_event_time_label(event, zone)}"
        )
        if len("\n".join([*lines, *additions])) > _HISTORY_TEXT_LIMIT:
            break
        lines.extend(additions)
        current_date = local.date()
        displayed += 1
    if len(visible) > displayed:
        lines.extend(["", f"Показаны последние {displayed} приёмов."])
    return "\n".join(lines), _history_keyboard(days)


def snooze_keyboard(event_id: object) -> InlineKeyboardMarkup:
    from uuid import UUID

    if not isinstance(event_id, UUID):
        raise ValueError("event_id must be UUID")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{SNOOZE} {minutes} мин",
                    callback_data=SnoozeCallback(event_id, minutes).encode(),
                    style=PRIMARY_STYLE,
                )
                for minutes in (15, 30, 60)
            ]
        ]
    )


def _history_keyboard(days: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(f"{DONE} " if days == value else "") + f"{value} дней",
                    callback_data=f"history:{value}",
                    style=PRIMARY_STYLE if days == value else None,
                )
                for value in (7, 30)
            ],
            [InlineKeyboardButton(text="Сегодня", callback_data="nav:today")],
        ]
    )


def _history_status_icon(status: IntakeEventStatus) -> str:
    if status is IntakeEventStatus.TAKEN:
        return DONE
    if status in {IntakeEventStatus.SKIPPED, IntakeEventStatus.MISSED}:
        return SKIPPED
    return PENDING


def _event_time_label(event: IntakeEvent, zone: ZoneInfo) -> str:
    scheduled_at = event.scheduled_at.astimezone(zone).strftime("%H:%M")
    if event.snoozed_until is not None:
        postponed = event.snoozed_until.astimezone(zone).strftime("%H:%M")
        return f"перенесено на {postponed} · план {scheduled_at}"
    if event.taken_at is None:
        return scheduled_at
    taken_at = event.taken_at.astimezone(zone).strftime("%H:%M")
    return f"принято {taken_at} · план {scheduled_at}"


def _action_label(action: EventAction, form: MedicationForm) -> str:
    if action is EventAction.UNDO:
        return "↩ Отменить приём"
    if action is EventAction.TAKE:
        return "Укол сделан" if form is MedicationForm.INJECTION else "Принять"
    if action is EventAction.SNOOZE:
        return "Отложить"
    return "Пропустить"


def _action_style(action: EventAction) -> str | None:
    if action is EventAction.TAKE:
        return SUCCESS_STYLE
    return None
