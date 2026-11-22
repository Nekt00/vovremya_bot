from dataclasses import dataclass
from datetime import time

MAX_TIMES_PER_RULE = 24


class InvalidScheduleRuleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DailyScheduleRule:
    times: tuple[time, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "times", _validate_times(self.times))


@dataclass(frozen=True, slots=True)
class IntervalScheduleRule:
    every_days: int
    times: tuple[time, ...]

    def __post_init__(self) -> None:
        if isinstance(self.every_days, bool) or not isinstance(self.every_days, int):
            raise InvalidScheduleRuleError("every_days must be a positive integer")
        if self.every_days <= 0:
            raise InvalidScheduleRuleError("every_days must be a positive integer")
        object.__setattr__(self, "times", _validate_times(self.times))


@dataclass(frozen=True, slots=True)
class WeekdayScheduleRule:
    weekdays: frozenset[int]
    times: tuple[time, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.weekdays, frozenset) or not self.weekdays:
            raise InvalidScheduleRuleError("weekdays must be a non-empty frozenset")
        if any(
            isinstance(weekday, bool) or not isinstance(weekday, int) or weekday not in range(1, 8)
            for weekday in self.weekdays
        ):
            raise InvalidScheduleRuleError("weekdays must use ISO values from 1 to 7")
        object.__setattr__(self, "times", _validate_times(self.times))


@dataclass(frozen=True, slots=True)
class WeeklyScheduleRule:
    times_by_weekday: tuple[tuple[int, tuple[time, ...]], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.times_by_weekday, tuple) or not self.times_by_weekday:
            raise InvalidScheduleRuleError("times_by_weekday must be a non-empty tuple")
        normalized: list[tuple[int, tuple[time, ...]]] = []
        weekdays: set[int] = set()
        for item in self.times_by_weekday:
            if not isinstance(item, tuple) or len(item) != 2:
                raise InvalidScheduleRuleError("weekday schedule entries must be pairs")
            weekday, times = item
            if (
                isinstance(weekday, bool)
                or not isinstance(weekday, int)
                or weekday not in range(1, 8)
            ):
                raise InvalidScheduleRuleError("weekdays must use ISO values from 1 to 7")
            if weekday in weekdays:
                raise InvalidScheduleRuleError("weekdays must be unique")
            weekdays.add(weekday)
            normalized.append((weekday, _validate_times(times)))
        object.__setattr__(self, "times_by_weekday", tuple(sorted(normalized)))

    @property
    def weekdays(self) -> frozenset[int]:
        return frozenset(weekday for weekday, _ in self.times_by_weekday)

    @property
    def times(self) -> tuple[time, ...]:
        return tuple(
            sorted({value for _, weekday_times in self.times_by_weekday for value in weekday_times})
        )

    def times_for_weekday(self, weekday: int) -> tuple[time, ...]:
        return next(
            (times for candidate, times in self.times_by_weekday if candidate == weekday),
            (),
        )


type ScheduleRule = (
    DailyScheduleRule | IntervalScheduleRule | WeekdayScheduleRule | WeeklyScheduleRule
)


def _validate_times(values: tuple[time, ...]) -> tuple[time, ...]:
    if not isinstance(values, tuple) or not values:
        raise InvalidScheduleRuleError("times must be a non-empty tuple")
    if len(values) > MAX_TIMES_PER_RULE:
        raise InvalidScheduleRuleError(
            f"a rule cannot contain more than {MAX_TIMES_PER_RULE} times"
        )
    for value in values:
        if not isinstance(value, time):
            raise InvalidScheduleRuleError("schedule times must be time values")
        if value.tzinfo is not None:
            raise InvalidScheduleRuleError("schedule times must be naive local times")
        if value.second != 0 or value.microsecond != 0:
            raise InvalidScheduleRuleError("schedule times must have minute precision")
        if value.fold != 0:
            raise InvalidScheduleRuleError("schedule times cannot define a DST fold")
    if len(set(values)) != len(values):
        raise InvalidScheduleRuleError("schedule times must be unique")
    return tuple(sorted(values))
