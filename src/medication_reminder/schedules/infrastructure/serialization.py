import re
from datetime import time
from typing import cast

from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    ScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class InvalidSchedulePayloadError(ValueError):
    pass


def serialize_schedule_rule(rule: ScheduleRule) -> tuple[str, JsonObject]:
    times: list[JsonValue] = [value.strftime("%H:%M") for value in rule.times]
    if isinstance(rule, DailyScheduleRule):
        return "daily", {"times": times}
    if isinstance(rule, IntervalScheduleRule):
        return "interval", {"every_days": rule.every_days, "times": times}
    if isinstance(rule, WeekdayScheduleRule):
        weekdays = cast(list[JsonValue], sorted(rule.weekdays))
        return "weekday", {"weekdays": weekdays, "times": times}
    if isinstance(rule, WeeklyScheduleRule):
        times_by_weekday: dict[str, JsonValue] = {
            str(weekday): [value.strftime("%H:%M") for value in weekday_times]
            for weekday, weekday_times in rule.times_by_weekday
        }
        return "weekday", {"times_by_weekday": times_by_weekday}
    raise TypeError(f"Unsupported schedule rule: {type(rule).__name__}")


def deserialize_schedule_rule(kind: str, payload: JsonObject) -> ScheduleRule:
    if kind == "daily":
        _require_exact_keys(payload, {"times"})
        return DailyScheduleRule(_parse_times(payload["times"]))
    if kind == "interval":
        _require_exact_keys(payload, {"every_days", "times"})
        every_days = payload["every_days"]
        if isinstance(every_days, bool) or not isinstance(every_days, int):
            raise InvalidSchedulePayloadError("every_days must be an integer")
        return IntervalScheduleRule(every_days, _parse_times(payload["times"]))
    if kind == "weekday":
        if set(payload) == {"times_by_weekday"}:
            value = payload["times_by_weekday"]
            if not isinstance(value, dict) or not value:
                raise InvalidSchedulePayloadError("times_by_weekday must be a non-empty object")
            entries: list[tuple[int, tuple[time, ...]]] = []
            for weekday, times_value in value.items():
                if not weekday.isascii() or not weekday.isdecimal():
                    raise InvalidSchedulePayloadError("weekday keys must be integers from 1 to 7")
                entries.append((int(weekday), _parse_times(times_value)))
            try:
                return WeeklyScheduleRule(tuple(entries))
            except ValueError as error:
                raise InvalidSchedulePayloadError(str(error)) from error
        _require_exact_keys(payload, {"weekdays", "times"})
        weekdays_value = payload["weekdays"]
        if not isinstance(weekdays_value, list) or any(
            isinstance(value, bool) or not isinstance(value, int) for value in weekdays_value
        ):
            raise InvalidSchedulePayloadError("weekdays must be a list of integers")
        if len(set(cast(list[int], weekdays_value))) != len(weekdays_value):
            raise InvalidSchedulePayloadError("weekdays must be unique")
        return WeekdayScheduleRule(
            frozenset(cast(list[int], weekdays_value)),
            _parse_times(payload["times"]),
        )
    raise InvalidSchedulePayloadError(f"Unknown schedule kind: {kind}")


def _parse_times(value: JsonValue) -> tuple[time, ...]:
    if not isinstance(value, list) or not value:
        raise InvalidSchedulePayloadError("times must be a non-empty list")
    parsed: list[time] = []
    for item in value:
        if not isinstance(item, str) or _TIME_PATTERN.fullmatch(item) is None:
            raise InvalidSchedulePayloadError("times must use strict HH:MM format")
        hour, minute = (int(part) for part in item.split(":"))
        parsed.append(time(hour, minute))
    return tuple(parsed)


def _require_exact_keys(payload: JsonObject, expected: set[str]) -> None:
    if set(payload) != expected:
        raise InvalidSchedulePayloadError(
            f"payload keys must be exactly: {', '.join(sorted(expected))}"
        )
