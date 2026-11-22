from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventStatus
from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.telegram.callbacks import EventAction, EventCallback
from medication_reminder.telegram.formatting import (
    allowed_actions,
    format_history,
    format_intake_detail,
    format_intake_editor,
    format_today,
)


def make_details(status: IntakeEventStatus) -> IntakeEventDetails:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    resolved_at = now if status.is_terminal else None
    snoozed_until = (
        datetime(2026, 10, 17, 9, tzinfo=UTC) if status is IntakeEventStatus.SNOOZED else None
    )
    return IntakeEventDetails(
        event=IntakeEvent(
            id=uuid4(),
            regimen_id=uuid4(),
            schedule_rule_id=uuid4(),
            sequence_number=1,
            scheduled_at=datetime(2026, 10, 17, 6, 30, tzinfo=UTC),
            timezone="Europe/Moscow",
            status=status,
            snoozed_until=snoozed_until,
            resolved_at=resolved_at,
            created_at=now,
            updated_at=now,
        ),
        medication_name="D3 <script>",
        medication_form=MedicationForm.TABLET,
        dose_amount=Decimal("2.00"),
        dose_unit="табл. & доза",
    )


def test_today_formatter_escapes_user_content_and_builds_actions() -> None:
    details = make_details(IntakeEventStatus.DUE)

    text, markup = format_today([details], "Europe/Moscow")

    assert "D3 &lt;script&gt;" in text
    assert "табл. &amp; доза" in text
    assert "09:30" in text
    assert "Выполнено: <b>0</b>" in text
    assert "Ожидает: <b>1</b>" in text
    assert "Не выполнено: <b>0</b>" in text  # noqa: RUF001
    assert markup is not None
    encoded = [button.callback_data for button in markup.inline_keyboard[0]]
    assert encoded == [EventCallback(details.event.id, EventAction.VIEW).encode()]


def test_selected_intake_has_actions_only_for_that_event() -> None:
    details = make_details(IntakeEventStatus.DUE)
    text, markup = format_intake_detail(details, "Europe/Moscow")
    assert "D3 &lt;script&gt;" in text
    encoded = [row[0].callback_data for row in markup.inline_keyboard[:-1]]
    assert encoded == [
        EventCallback(details.event.id, EventAction.TAKE).encode(),
        EventCallback(details.event.id, EventAction.SNOOZE).encode(),
        EventCallback(details.event.id, EventAction.SKIP).encode(),
    ]
    assert [row[0].style for row in markup.inline_keyboard[:-1]] == [
        "success",
        None,
        None,
    ]
    assert [row[0].text for row in markup.inline_keyboard[:-1]] == [
        "Принять",
        "Отложить",
        "Пропустить",
    ]


def test_taken_event_has_only_editor_entry_on_today_screen() -> None:
    text, markup = format_today([make_details(IntakeEventStatus.TAKEN)], "Europe/Moscow")

    assert markup is not None
    assert markup.inline_keyboard[0][0].text == "Отметить приём вручную"
    assert markup.inline_keyboard[0][0].callback_data == "intakes:edit"
    assert "Выполнено: <b>1</b>" in text
    assert "принято 11:00 · план 09:30" in text
    assert allowed_actions(IntakeEventStatus.TAKEN) == ()


def test_intake_editor_includes_taken_and_pending_events_with_explicit_toggle_actions() -> None:
    taken = make_details(IntakeEventStatus.TAKEN)
    evening = make_details(IntakeEventStatus.SCHEDULED)
    evening = replace(
        evening, event=replace(evening.event, scheduled_at=datetime(2026, 10, 17, 18, tzinfo=UTC))
    )
    _, markup = format_intake_editor([evening, taken], "Europe/Moscow")
    buttons = [row[0] for row in markup.inline_keyboard]
    assert (
        buttons[0].callback_data
        == f"edit:{EventCallback(taken.event.id, EventAction.UNDO).encode()}"
    )
    assert (
        buttons[1].callback_data
        == f"edit:{EventCallback(evening.event.id, EventAction.TAKE).encode()}"
    )
    assert "21:00" in buttons[1].text
    assert buttons[-1].callback_data == "nav:today"
    _, after_undo = format_intake_editor(
        [
            replace(
                taken,
                event=replace(taken.event, status=IntakeEventStatus.SCHEDULED, resolved_at=None),
            )
        ],
        "Europe/Moscow",
    )
    assert (
        after_undo.inline_keyboard[0][0].callback_data
        == f"edit:{EventCallback(taken.event.id, EventAction.TAKE).encode()}"
    )


def test_today_summarizes_failed_intakes_and_hides_cancelled_events() -> None:
    text, markup = format_today(
        [
            make_details(IntakeEventStatus.SKIPPED),
            make_details(IntakeEventStatus.MISSED),
            make_details(IntakeEventStatus.CANCELLED),
        ],
        "Europe/Moscow",
    )

    assert "Не выполнено: <b>2</b>" in text  # noqa: RUF001
    assert text.count("D3 &lt;script&gt;") == 2
    assert markup is not None
    assert any(
        button.callback_data == "intakes:edit" for row in markup.inline_keyboard for button in row
    )


def test_empty_current_window_still_allows_editing_other_today_intakes() -> None:
    text, markup = format_today([], "Europe/Moscow")

    assert "На сегодня приёмов нет" in text  # noqa: RUF001
    assert markup is not None
    assert markup.inline_keyboard[0][0].callback_data == "intakes:edit"


def test_today_shows_new_time_for_a_postponed_intake() -> None:
    text, _ = format_today([make_details(IntakeEventStatus.SNOOZED)], "Europe/Moscow")
    assert "перенесено на 12:00 · план 09:30" in text


def test_history_summarizes_statuses_and_builds_period_switcher() -> None:
    details = [
        make_details(IntakeEventStatus.TAKEN),
        make_details(IntakeEventStatus.SKIPPED),
        make_details(IntakeEventStatus.DUE),
        make_details(IntakeEventStatus.CANCELLED),
    ]

    text, markup = format_history(details, "Europe/Moscow", days=7)

    assert "Выполнено: <b>1</b>" in text
    assert "Пропущено: <b>1</b>" in text
    assert "Ожидает: <b>1</b>" in text
    assert "Соблюдение графика: <b>50%</b>" in text
    assert text.count("D3 &lt;script&gt;") == 3
    assert [button.callback_data for button in markup.inline_keyboard[0]] == [
        "history:7",
        "history:30",
    ]
    assert [button.style for button in markup.inline_keyboard[0]] == ["primary", None]


def test_empty_history_has_period_switcher() -> None:
    text, markup = format_history([], "Europe/Moscow", days=30)

    assert "За выбранный период приёмов нет" in text  # noqa: RUF001
    assert markup.inline_keyboard[0][1].text == "✅ 30 дней"


def test_history_stays_below_telegram_message_limit() -> None:
    item = replace(
        make_details(IntakeEventStatus.TAKEN),
        medication_name="&" * 120,
    )

    text, _ = format_history([item] * 50, "Europe/Moscow", days=30)

    assert len(text) < 4_096
    assert "Показаны последние" in text
