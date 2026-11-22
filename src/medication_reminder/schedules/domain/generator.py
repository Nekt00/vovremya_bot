from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from medication_reminder.regimens.domain.regimen import Regimen, RegimenStatus
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    ScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.shared.timezones import validate_timezone

MAX_SCANNED_DAYS = 3660
MAX_GENERATED_OCCURRENCES = 100_000


class InvalidGenerationWindowError(ValueError):
    pass


class ScheduleGenerationLimitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Occurrence:
    sequence_number: int
    scheduled_local: datetime
    scheduled_at: datetime


def generate_occurrences(
    regimen: Regimen,
    rule: ScheduleRule,
    timezone: str,
    *,
    window_end: datetime,
    window_start: datetime | None = None,
    count_before_window: bool = True,
) -> tuple[Occurrence, ...]:
    zone = ZoneInfo(validate_timezone(timezone))
    end_utc = _as_utc_window_boundary(window_end, "window_end")
    start_utc = (
        _as_utc_window_boundary(window_start, "window_start") if window_start is not None else None
    )
    if start_utc is not None and start_utc > end_utc:
        raise InvalidGenerationWindowError("window_start cannot be after window_end")
    if regimen.status is not RegimenStatus.ACTIVE:
        return ()

    last_local_date = end_utc.astimezone(zone).date()
    if regimen.end_date is not None:
        last_local_date = min(last_local_date, regimen.end_date)
    if last_local_date < regimen.start_date:
        return ()

    occurrences: list[Occurrence] = []
    sequence_number = 0
    current_date = regimen.start_date
    scanned_days = 0

    while current_date <= last_local_date:
        scanned_days += 1
        if scanned_days > MAX_SCANNED_DAYS:
            raise ScheduleGenerationLimitError(
                f"generation cannot scan more than {MAX_SCANNED_DAYS} calendar days"
            )

        times = _times_for_date(current_date, regimen.start_date, rule)
        if times:
            for local_time in times:
                scheduled_local = _resolve_local_datetime(
                    datetime.combine(current_date, local_time),
                    zone,
                )
                scheduled_at = scheduled_local.astimezone(UTC)
                if count_before_window:
                    sequence_number += 1
                    if (
                        regimen.total_intakes is not None
                        and sequence_number > regimen.total_intakes
                    ):
                        return tuple(occurrences)
                if scheduled_at > end_utc:
                    continue
                if start_utc is not None and scheduled_at < start_utc:
                    continue
                if not count_before_window:
                    sequence_number += 1
                    if (
                        regimen.total_intakes is not None
                        and sequence_number > regimen.total_intakes
                    ):
                        return tuple(occurrences)
                if sequence_number > MAX_GENERATED_OCCURRENCES:
                    raise ScheduleGenerationLimitError(
                        f"generation cannot exceed {MAX_GENERATED_OCCURRENCES} occurrences"
                    )
                occurrences.append(
                    Occurrence(
                        sequence_number=sequence_number,
                        scheduled_local=scheduled_local,
                        scheduled_at=scheduled_at,
                    )
                )
        current_date += timedelta(days=1)

    return tuple(occurrences)


def _times_for_date(
    current: date,
    course_start: date,
    rule: ScheduleRule,
) -> tuple[time, ...]:
    if isinstance(rule, DailyScheduleRule):
        return rule.times
    if isinstance(rule, IntervalScheduleRule):
        return rule.times if (current - course_start).days % rule.every_days == 0 else ()
    if isinstance(rule, WeekdayScheduleRule):
        return rule.times if current.isoweekday() in rule.weekdays else ()
    if isinstance(rule, WeeklyScheduleRule):
        return rule.times_for_weekday(current.isoweekday())
    raise TypeError(f"Unsupported schedule rule: {type(rule).__name__}")


def _resolve_local_datetime(local_naive: datetime, zone: ZoneInfo) -> datetime:
    fold_zero = local_naive.replace(tzinfo=zone, fold=0)
    fold_one = local_naive.replace(tzinfo=zone, fold=1)
    round_trip_zero = fold_zero.astimezone(UTC).astimezone(zone)
    round_trip_one = fold_one.astimezone(UTC).astimezone(zone)

    zero_is_valid = round_trip_zero.replace(tzinfo=None) == local_naive
    one_is_valid = round_trip_one.replace(tzinfo=None) == local_naive
    if zero_is_valid:
        return fold_zero
    if one_is_valid:
        return fold_one

    shifted_forward = [
        candidate
        for candidate in (round_trip_zero, round_trip_one)
        if candidate.replace(tzinfo=None) > local_naive
    ]
    if not shifted_forward:
        raise ValueError(f"Could not resolve nonexistent local time {local_naive!s}")
    return min(shifted_forward, key=lambda candidate: candidate.replace(tzinfo=None))


def _as_utc_window_boundary(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidGenerationWindowError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)
