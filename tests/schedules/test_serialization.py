from datetime import time

import pytest

from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    ScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.schedules.infrastructure.serialization import (
    InvalidSchedulePayloadError,
    deserialize_schedule_rule,
    serialize_schedule_rule,
)


@pytest.mark.parametrize(
    "rule",
    [
        DailyScheduleRule((time(9), time(21, 30))),
        IntervalScheduleRule(3, (time(10),)),
        WeekdayScheduleRule(frozenset({1, 3, 5}), (time(8, 15),)),
        WeeklyScheduleRule(((1, (time(6),)), (6, (time(9),)), (7, (time(9),)))),
    ],
)
def test_schedule_rule_serialization_round_trip(rule: ScheduleRule) -> None:
    kind, payload = serialize_schedule_rule(rule)

    assert deserialize_schedule_rule(kind, payload) == rule


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("unknown", {"times": ["09:00"]}),
        ("daily", {"times": ["9:00"]}),
        ("daily", {"times": ["09:00"], "unexpected": True}),
        ("interval", {"every_days": True, "times": ["09:00"]}),
        ("weekday", {"weekdays": [1, "3"], "times": ["09:00"]}),
        ("weekday", {"times_by_weekday": {"monday": ["09:00"]}}),
    ],
)
def test_deserializer_rejects_malformed_payload(kind: str, payload: dict[str, object]) -> None:
    with pytest.raises((InvalidSchedulePayloadError, ValueError)):
        deserialize_schedule_rule(kind, payload)  # type: ignore[arg-type]
