from datetime import time
from decimal import Decimal

from medication_reminder.schedules.domain.rules import (
    IntervalScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.telegram.medication_set_views import parse_time
from medication_reminder.telegram.regimen_edit_forms import revision_values, summary_text


def test_revision_values_build_dose_and_interval_rule() -> None:
    dose, rule = revision_values(
        {
            "new_dose": "2.5",
            "schedule_kind": "i",
            "every_days": 3,
            "times": "06:00, 21:00",
        }
    )

    assert dose == Decimal("2.5")
    assert rule == IntervalScheduleRule(3, (time(6), time(21)))


def test_revision_values_build_weekday_rule_without_dose_change() -> None:
    dose, rule = revision_values(
        {
            "schedule_kind": "w",
            "weekdays": [1, 3, 5],
            "times": "06:00",
        }
    )

    assert dose is None
    assert rule == WeekdayScheduleRule(frozenset({1, 3, 5}), (time(6),))


def test_edit_summary_describes_only_future_changes() -> None:
    text = summary_text({"new_dose": "1.5"})

    assert "1.5" in text
    assert "только будущие" in text


def test_revision_values_build_workday_and_weekend_rule() -> None:
    dose, rule = revision_values(
        {
            "schedule_kind": "x",
            "workday_times": "06:30",
            "weekend_times": "09:00, 21:00",
        }
    )

    assert dose is None
    assert isinstance(rule, WeeklyScheduleRule)
    assert rule.times_for_weekday(1) == (time(6, 30),)
    assert rule.times_for_weekday(7) == (time(9), time(21))
    assert "будни 06:30; выходные 09:00, 21:00" in summary_text(
        {
            "schedule_kind": "x",
            "workday_times": "06:30",
            "weekend_times": "09:00, 21:00",
        }
    )


def test_medication_set_time_accepts_flexible_hour_format() -> None:
    assert parse_time("5:30") == time(5, 30)
    assert parse_time(" 23:05 ") == time(23, 5)


def test_medication_set_time_rejects_invalid_values() -> None:
    for value in ("", "24:00", "10:60", "утро"):
        try:
            parse_time(value)
        except ValueError:
            continue
        raise AssertionError(f"Expected invalid time: {value}")
