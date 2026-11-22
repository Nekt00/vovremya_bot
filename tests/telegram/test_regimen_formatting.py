from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventStatus
from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.schedules.domain.rules import IntervalScheduleRule
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.telegram.callbacks import RegimenAction, RegimenCallback
from medication_reminder.telegram.regimen_formatting import (
    completion_confirmation,
    deletion_confirmation,
    format_regimen_details,
    format_regimen_list,
)
from medication_reminder.telegram.regimen_service import RegimenDetails


def make_details(
    status: RegimenStatus = RegimenStatus.ACTIVE,
    *,
    next_scheduled_at: datetime | None = None,
) -> RegimenDetails:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    regimen = Regimen(
        id=uuid4(),
        user_id=uuid4(),
        medication_name="Укол <X>",
        medication_form=MedicationForm.INJECTION,
        dose_amount=Decimal("1.00"),
        dose_unit="мг",
        start_date=date(2026, 10, 20),
        total_intakes=35,
        end_date=None,
        status=status,
        created_at=now,
        updated_at=now,
    )
    schedule = StoredScheduleRule(
        id=uuid4(),
        regimen_id=regimen.id,
        rule=IntervalScheduleRule(3, (time(6),)),
        timezone="Europe/Moscow",
        version=1,
        active=True,
        created_at=now,
    )
    next_event = (
        IntakeEvent(
            id=uuid4(),
            regimen_id=regimen.id,
            schedule_rule_id=schedule.id,
            sequence_number=1,
            scheduled_at=next_scheduled_at,
            timezone="Europe/Moscow",
            status=IntakeEventStatus.SCHEDULED,
            snoozed_until=None,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )
        if next_scheduled_at is not None
        else None
    )
    return RegimenDetails(regimen, schedule, next_event)


def test_regimen_details_show_schedule_and_safe_actions() -> None:
    details = make_details(next_scheduled_at=datetime(2026, 10, 20, 3, tzinfo=UTC))

    text, keyboard = format_regimen_details(details)

    assert "Укол &lt;X&gt;" in text
    assert "каждые 3 дн. в 06:00" in text
    assert "20.10.2026 в 06:00" in text
    assert "35 приёмов" in text
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert RegimenCallback(details.regimen.id, RegimenAction.EDIT).encode() in callbacks
    assert RegimenCallback(details.regimen.id, RegimenAction.PAUSE).encode() in callbacks
    assert RegimenCallback(details.regimen.id, RegimenAction.COMPLETE).encode() in callbacks
    assert keyboard.inline_keyboard[0][0].style == "primary"
    assert keyboard.inline_keyboard[-2][0].style == "danger"


def test_completed_regimen_can_only_be_deleted_or_open_list() -> None:
    details = make_details(RegimenStatus.COMPLETED)

    _, keyboard = format_regimen_details(details)

    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks[0] is not None and callbacks[0].startswith("rg:d:")
    assert callbacks[1:] == ["rg:list"]


def test_completion_requires_confirmation() -> None:
    details = make_details()

    text, keyboard = completion_confirmation(details)

    assert "нельзя отменить" in text
    assert (
        keyboard.inline_keyboard[0][0].callback_data
        == RegimenCallback(details.regimen.id, RegimenAction.CONFIRM_COMPLETE).encode()
    )
    assert keyboard.inline_keyboard[0][0].text.endswith("Завершить курс")


def test_deletion_confirmation_names_the_action() -> None:
    details = make_details()

    text, keyboard = deletion_confirmation(details)

    assert "Удалить курс" in text
    assert keyboard.inline_keyboard[0][0].text.endswith("Удалить курс")


def test_regimen_list_escapes_names_through_button_text() -> None:
    details = make_details()

    text, keyboard = format_regimen_list([details.regimen])

    assert "Курсы" in text
    assert keyboard is not None
    assert "Укол <X>" in keyboard.inline_keyboard[0][0].text


def test_family_assignment_is_read_only_for_recipient() -> None:
    original = make_details()
    details = RegimenDetails(
        original.regimen,
        original.schedule,
        original.next_event,
        can_manage=False,
        family_assignment=True,
    )

    text, keyboard = format_regimen_details(details)

    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "только владелец семейной группы" in text
    assert callbacks == ["rg:list"]


def test_family_owner_can_manage_assignment_and_return_to_family() -> None:
    original = make_details()
    details = RegimenDetails(
        original.regimen,
        original.schedule,
        original.next_event,
        can_manage=True,
        family_assignment=True,
    )

    _, keyboard = format_regimen_details(details)

    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert RegimenCallback(details.regimen.id, RegimenAction.EDIT).encode() in callbacks
    assert callbacks[-1] == "family:home"
