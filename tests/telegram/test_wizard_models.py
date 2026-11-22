from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest

from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.telegram.wizard_models import (
    COMMON_TIMES,
    QUICK_DOSE_AMOUNTS,
    EndingKind,
    NewRegimenCommand,
    ScheduleKind,
    WizardValidationError,
    build_rule,
    command_from_state,
    format_summary,
    parse_dose_amount,
    parse_local_date,
    parse_quick_dose,
    parse_times,
    require_not_past,
    required_horizon_days,
    toggle_time,
    toggle_weekday,
)
from medication_reminder.telegram.wizard_service import materialization_window_end
from medication_reminder.telegram.wizard_ui import (
    dose_amount_keyboard,
    reminder_target_keyboard,
    schedule_keyboard,
    times_keyboard,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", Decimal("1")), ("2,5", Decimal("2.5")), ("0.125", Decimal("0.125"))],
)
def test_parse_dose_amount_accepts_dot_and_comma(raw: str, expected: Decimal) -> None:
    assert parse_dose_amount(raw) == expected


@pytest.mark.parametrize("raw", ["0", "-1", "1e2", "nan", "1,2,3", "1234567890"])
def test_parse_dose_amount_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(WizardValidationError):
        parse_dose_amount(raw)


def test_quick_dose_amounts_are_validated_options() -> None:
    assert QUICK_DOSE_AMOUNTS == ("0.5", "1", "2", "5")
    assert [parse_quick_dose(value) for value in QUICK_DOSE_AMOUNTS] == [
        Decimal("0.5"),
        Decimal("1"),
        Decimal("2"),
        Decimal("5"),
    ]
    with pytest.raises(WizardValidationError):
        parse_quick_dose("10")

    callbacks = [
        button.callback_data for row in dose_amount_keyboard().inline_keyboard for button in row
    ]
    assert "w:dose:0.5" in callbacks
    assert "w:dose:custom" in callbacks


def test_date_parser_is_strict_and_past_check_uses_users_timezone() -> None:
    now = datetime(2026, 10, 16, 21, 30, tzinfo=UTC)

    assert parse_local_date("17.10.2026") == date(2026, 10, 17)
    with pytest.raises(WizardValidationError):
        parse_local_date("17.1.2026")
    with pytest.raises(WizardValidationError, match="прошлом"):
        require_not_past(date(2026, 10, 16), now=now, timezone="Europe/Moscow")


def test_time_parser_sorts_and_requires_unique_minute_precision() -> None:
    assert parse_times("21:00, 09:05") == (time(9, 5), time(21))
    with pytest.raises(WizardValidationError):
        parse_times("09:00, 09:00")
    with pytest.raises(WizardValidationError):
        parse_times("09:00:30")


def test_common_time_multi_select_includes_0600_and_toggles() -> None:
    six = time(6)
    assert six in COMMON_TIMES

    selected = toggle_time((), six)
    selected = toggle_time(selected, time(21))

    assert selected == (six, time(21))
    assert toggle_time(selected, six) == (time(21),)

    keyboard = times_keyboard(selected)
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert any(
        button.text == "✅ 06:00" and button.callback_data == "w:time:0600" for button in buttons
    )
    assert any(button.callback_data == "w:time:custom" for button in buttons)


def test_custom_time_accepts_0500_and_0600() -> None:
    assert parse_times("05:00, 06:00") == (time(5), time(6))


def test_set_path_offers_morning_day_evening_or_exact_time() -> None:
    keyboard = reminder_target_keyboard([])
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert callbacks == [
        "w:target:morning",
        "w:target:day",
        "w:target:evening",
        "w:target:exact",
        "w:cancel",
    ]


def test_set_schedule_does_not_offer_different_workday_and_weekend_times() -> None:
    callbacks = [
        button.callback_data
        for row in schedule_keyboard(allow_weekly=False).inline_keyboard
        for button in row
    ]

    assert "w:schedule:x" not in callbacks
    assert callbacks == ["w:schedule:d", "w:schedule:i", "w:schedule:w", "w:cancel"]


def test_weekday_toggle_adds_and_removes_selection() -> None:
    assert toggle_weekday(frozenset(), 1) == frozenset({1})
    assert toggle_weekday(frozenset({1, 3}), 1) == frozenset({3})
    with pytest.raises(WizardValidationError):
        toggle_weekday(frozenset(), 8)


def test_build_rule_supports_all_schedule_kinds() -> None:
    times = (time(9),)

    assert isinstance(build_rule(ScheduleKind.DAILY, times), DailyScheduleRule)
    assert isinstance(build_rule(ScheduleKind.INTERVAL, times, every_days=3), IntervalScheduleRule)
    assert isinstance(
        build_rule(ScheduleKind.WEEKDAYS, times, weekdays=frozenset({1, 5})),
        WeekdayScheduleRule,
    )
    assert isinstance(
        build_rule(
            ScheduleKind.WEEKLY,
            (),
            workday_times=(time(6),),
            weekend_times=(time(9),),
        ),
        WeeklyScheduleRule,
    )


def test_command_boundary_builds_typed_weekday_command() -> None:
    command = command_from_state(
        {
            "medication_name": "Магний",
            "medication_form": "tablet",
            "dose_amount": "2.5",
            "dose_unit": "таблетки",
            "start_date": "17.10.2026",
            "schedule_kind": "w",
            "weekdays": [1, 3, 5],
            "times": "09:00, 21:00",
            "ending_kind": "o",
        }
    )

    assert isinstance(command.rule, WeekdayScheduleRule)
    assert command.rule.weekdays == frozenset({1, 3, 5})


def test_command_builds_workday_and_weekend_schedule() -> None:
    command = command_from_state(
        {
            "medication_name": "Витамин D",
            "medication_form": "tablet",
            "dose_amount": "1",
            "dose_unit": "таблетка",
            "start_date": "17.10.2026",
            "schedule_kind": "x",
            "workday_times": "06:30",
            "weekend_times": "09:00",
            "ending_kind": "o",
        }
    )

    assert isinstance(command.rule, WeeklyScheduleRule)
    assert command.rule.times_for_weekday(1) == (time(6, 30),)
    assert command.rule.times_for_weekday(6) == (time(9),)
    assert "будни в 06:30; выходные в 09:00" in format_summary(command)


def test_command_uses_set_window_start_as_internal_schedule_time() -> None:
    set_id = "00000000-0000-0000-0000-000000000123"
    command = command_from_state(
        {
            "medication_name": "Витамин D",
            "medication_form": "tablet",
            "dose_amount": "2",
            "dose_unit": "таблетка",
            "start_date": "17.10.2026",
            "reminder_mode": "set",
            "medication_set_id": set_id,
            "medication_set_name": "Утро",
            "medication_set_window_start": "06:00",
            "medication_set_window_end": "12:00",
            "schedule_kind": "d",
            "times": "06:00",
            "ending_kind": "c",
            "total_intakes": 30,
        }
    )

    assert isinstance(command.rule, DailyScheduleRule)
    assert command.rule.times == (time(6),)
    assert command.medication_set is not None
    assert str(command.medication_set.set_id) == set_id
    summary = format_summary(command)
    assert "График: ежедневно" in summary
    assert "<b>Утро</b>" in summary
    assert "06:00" in summary
    assert "12:00" in summary


def test_35_intakes_every_three_days_has_sufficient_bounded_horizon() -> None:
    command = _command(
        rule=IntervalScheduleRule(3, (time(10),)),
        total_intakes=35,
    )

    assert required_horizon_days(command) == 103
    assert materialization_window_end(command, "Europe/Moscow") == datetime(
        2027, 1, 30, 20, 59, 59, 999999, tzinfo=UTC
    )


def test_open_ended_course_materializes_exactly_90_calendar_days() -> None:
    command = _command(rule=DailyScheduleRule((time(10),)))

    assert required_horizon_days(command) == 90
    assert materialization_window_end(command, "Europe/Moscow") == datetime(
        2027, 1, 17, 20, 59, 59, 999999, tzinfo=UTC
    )


def test_summary_escapes_user_text_and_formats_integral_dose() -> None:
    command = NewRegimenCommand(
        medication_name="D3 <b>unsafe</b>",
        medication_form=MedicationForm.TABLET,
        dose_amount=Decimal("10.00"),
        dose_unit="табл. & доза",
        start_date=date(2026, 10, 17),
        rule=DailyScheduleRule((time(9),)),
        total_intakes=None,
        end_date=None,
    )

    result = format_summary(command)

    assert "D3 &lt;b&gt;unsafe&lt;/b&gt;" in result
    assert "10 табл. &amp; доза" in result
    assert EndingKind.OPEN_ENDED.value == "o"


def _command(
    *,
    rule: DailyScheduleRule | IntervalScheduleRule,
    total_intakes: int | None = None,
) -> NewRegimenCommand:
    return NewRegimenCommand(
        medication_name="Препарат",
        medication_form=MedicationForm.INJECTION,
        dose_amount=Decimal("1"),
        dose_unit="мг",
        start_date=date(2026, 10, 20),
        rule=rule,
        total_intakes=total_intakes,
        end_date=None,
    )
