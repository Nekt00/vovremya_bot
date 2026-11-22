from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from medication_reminder.shared.timezones import validate_timezone

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_day_utc_bounds(now: datetime, timezone: str) -> tuple[datetime, datetime]:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo(validate_timezone(timezone))
    local_date = now.astimezone(zone).date()
    local_start = datetime.combine(local_date, time.min, zone)
    local_end = datetime.combine(local_date + timedelta(days=1), time.min, zone)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)
