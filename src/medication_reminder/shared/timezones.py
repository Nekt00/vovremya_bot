from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidTimezoneError(ValueError):
    pass


def validate_timezone(timezone: str) -> str:
    if not timezone or timezone != timezone.strip():
        raise InvalidTimezoneError("Timezone must be a non-empty IANA identifier")

    try:
        zone = ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise InvalidTimezoneError(f"Unknown IANA timezone: {timezone}") from error

    return zone.key
