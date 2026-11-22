from datetime import UTC, time

import pytest

from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    InvalidScheduleRuleError,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)


def test_times_are_normalized_to_sorted_order() -> None:
    rule = DailyScheduleRule((time(21), time(9)))

    assert rule.times == (time(9), time(21))


@pytest.mark.parametrize(
    "times",
    [
        (),
        (time(9), time(9)),
        (time(9, 0, 1),),
        (time(9, tzinfo=UTC),),
    ],
)
def test_rule_rejects_invalid_times(times: tuple[time, ...]) -> None:
    with pytest.raises(InvalidScheduleRuleError):
        DailyScheduleRule(times)


@pytest.mark.parametrize("every_days", [0, -1, True])
def test_interval_requires_positive_integer(every_days: int) -> None:
    with pytest.raises(InvalidScheduleRuleError):
        IntervalScheduleRule(every_days, (time(9),))


@pytest.mark.parametrize("weekdays", [frozenset(), frozenset({0}), frozenset({8})])
def test_weekdays_use_iso_range(weekdays: frozenset[int]) -> None:
    with pytest.raises(InvalidScheduleRuleError):
        WeekdayScheduleRule(weekdays, (time(9),))


def test_weekly_rule_normalizes_day_specific_times() -> None:
    rule = WeeklyScheduleRule(((6, (time(10),)), (1, (time(8), time(6))), (7, (time(10),))))

    assert rule.times_for_weekday(1) == (time(6), time(8))
    assert rule.times_for_weekday(6) == (time(10),)
    assert rule.times_for_weekday(2) == ()
    assert rule.times == (time(6), time(8), time(10))


def test_weekly_rule_rejects_duplicate_weekdays() -> None:
    with pytest.raises(InvalidScheduleRuleError):
        WeeklyScheduleRule(((1, (time(6),)), (1, (time(9),))))
