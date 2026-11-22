from medication_reminder.shared.timezones import (
    InvalidTimezoneError as InvalidTimezoneError,
)
from medication_reminder.shared.timezones import validate_timezone as validate_timezone


class InvalidTelegramUserIdError(ValueError):
    pass


def validate_telegram_user_id(telegram_user_id: int) -> int:
    if (
        not isinstance(telegram_user_id, int)
        or isinstance(telegram_user_id, bool)
        or telegram_user_id <= 0
    ):
        raise InvalidTelegramUserIdError("Telegram user ID must be a positive integer")
    return telegram_user_id
