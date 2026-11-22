from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from medication_reminder.users.domain.user import User
from medication_reminder.users.domain.validation import InvalidTimezoneError


def test_user_requires_utc_timestamps() -> None:
    non_utc = datetime.now(timezone(timedelta(hours=3)))

    with pytest.raises(ValueError, match="created_at must be timezone-aware and in UTC"):
        User(uuid4(), 123, None, non_utc, datetime.now(UTC))


def test_user_rejects_invalid_timezone() -> None:
    now = datetime.now(UTC)

    with pytest.raises(InvalidTimezoneError):
        User(uuid4(), 123, "Moscow", now, now)
