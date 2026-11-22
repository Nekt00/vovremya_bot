from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.reminders.formatting import format_reminder, format_set_reminder
from medication_reminder.reminders.repository import (
    ClaimedReminder,
    ClaimedSetReminder,
    SetReminderItem,
)
from medication_reminder.telegram.callbacks import (
    EventAction,
    EventCallback,
    SetTakeAllCallback,
)


def test_reminder_contains_escaped_details_local_time_and_actions() -> None:
    event_id = uuid4()
    reminder = ClaimedReminder(
        attempt_id=uuid4(),
        claim_token=uuid4(),
        event_id=event_id,
        telegram_user_id=42,
        medication_name="D3 <script>",
        medication_form=MedicationForm.TABLET,
        dose_amount=Decimal("2.00"),
        dose_unit="табл. & доза",
        scheduled_at=datetime(2026, 10, 17, 6, tzinfo=UTC),
        timezone="Europe/Moscow",
    )

    text, keyboard = format_reminder(reminder)

    assert "D3 &lt;script&gt;" in text
    assert "табл. &amp; доза" in text
    assert "09:00" in text
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == [
        EventCallback(event_id, EventAction.TAKE).encode(),
        EventCallback(event_id, EventAction.SNOOZE).encode(),
        EventCallback(event_id, EventAction.SKIP).encode(),
    ]
    assert [button.style for row in keyboard.inline_keyboard for button in row] == [
        "success",
        None,
        None,
    ]


def test_set_reminder_contains_items_window_and_take_actions() -> None:
    first_event_id = uuid4()
    second_event_id = uuid4()
    set_id = uuid4()
    local_date = date(2026, 10, 17)
    reminder = ClaimedSetReminder(
        attempt_id=uuid4(),
        claim_token=uuid4(),
        set_id=set_id,
        set_name="Утро <важное>",
        local_date=local_date,
        telegram_user_id=42,
        window_end=datetime(2026, 10, 17, 9, tzinfo=UTC),
        timezone="Europe/Moscow",
        items=(
            SetReminderItem(
                first_event_id,
                "Витамин D3 & K2",
                MedicationForm.TABLET,
                Decimal("2"),
                "табл.",
            ),
            SetReminderItem(
                second_event_id,
                "Инсулин",
                MedicationForm.INJECTION,
                Decimal("5"),
                "мл",
            ),
        ),
    )

    text, keyboard = format_set_reminder(reminder)

    assert "Утро &lt;важное&gt;" in text
    assert "Витамин D3 &amp; K2" in text
    assert "Инсулин" in text
    assert "до <b>12:00</b>" in text
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == [
        EventCallback(first_event_id, EventAction.VIEW).encode(),
        EventCallback(second_event_id, EventAction.VIEW).encode(),
        SetTakeAllCallback(set_id, local_date).encode(),
    ]
    assert [button.style for row in keyboard.inline_keyboard for button in row] == [
        None,
        None,
        "success",
    ]
