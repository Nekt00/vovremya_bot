from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from medication_reminder.telegram.callbacks import (
    EventAction,
    EventCallback,
    RegimenAction,
    RegimenCallback,
    SetTakeAllCallback,
    SnoozeCallback,
)
from medication_reminder.telegram.clock import local_day_utc_bounds


def test_callback_round_trip_is_compact() -> None:
    callback = EventCallback(uuid4(), EventAction.SNOOZE)

    encoded = callback.encode()

    assert EventCallback.decode(encoded) == callback
    assert len(encoded.encode()) <= 64


@pytest.mark.parametrize(
    "value",
    ["", "ie:t", "other:t:00000000-0000-0000-0000-000000000000", "ie:x:nope"],
)
def test_callback_rejects_invalid_payload(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid intake event callback"):
        EventCallback.decode(value)


@pytest.mark.parametrize("minutes", [15, 30, 60])
def test_snooze_callback_round_trip(minutes: int) -> None:
    callback = SnoozeCallback(uuid4(), minutes)

    assert SnoozeCallback.decode(callback.encode()) == callback


@pytest.mark.parametrize("value", ["is:10:00000000-0000-0000-0000-000000000000", "is:x:nope"])
def test_snooze_callback_rejects_unapproved_duration(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid snooze callback"):
        SnoozeCallback.decode(value)


@pytest.mark.parametrize("action", list(RegimenAction))
def test_regimen_callback_round_trip(action: RegimenAction) -> None:
    callback = RegimenCallback(uuid4(), action)

    encoded = callback.encode()

    assert RegimenCallback.decode(encoded) == callback
    assert len(encoded.encode()) <= 64


@pytest.mark.parametrize("value", ["", "rg:v", "rg:x:nope", "rg:list"])
def test_regimen_callback_rejects_invalid_payload(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid regimen callback"):
        RegimenCallback.decode(value)


def test_set_take_all_callback_round_trip_is_compact() -> None:
    callback = SetTakeAllCallback(uuid4(), date(2026, 10, 17))

    encoded = callback.encode()

    assert SetTakeAllCallback.decode(encoded) == callback
    assert len(encoded.encode()) <= 64


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sa:20261017",
        "other:20261017:00000000-0000-0000-0000-000000000000",
        "sa:20261340:00000000-0000-0000-0000-000000000000",
        "sa:2026-10-17:00000000-0000-0000-0000-000000000000",
    ],
)
def test_set_take_all_callback_rejects_invalid_payload(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid set callback"):
        SetTakeAllCallback.decode(value)


def test_local_day_bounds_for_regular_timezone() -> None:
    start, end = local_day_utc_bounds(
        datetime(2026, 10, 17, 12, tzinfo=UTC),
        "Europe/Moscow",
    )

    assert start == datetime(2026, 10, 16, 21, tzinfo=UTC)
    assert end == datetime(2026, 10, 17, 21, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "expected_start", "expected_end"),
    [
        (
            datetime(2026, 3, 29, 12, tzinfo=UTC),
            datetime(2026, 3, 28, 23, tzinfo=UTC),
            datetime(2026, 3, 29, 22, tzinfo=UTC),
        ),
        (
            datetime(2026, 10, 25, 12, tzinfo=UTC),
            datetime(2026, 10, 24, 22, tzinfo=UTC),
            datetime(2026, 10, 25, 23, tzinfo=UTC),
        ),
    ],
)
def test_local_day_bounds_follow_dst(
    now: datetime,
    expected_start: datetime,
    expected_end: datetime,
) -> None:
    assert local_day_utc_bounds(now, "Europe/Berlin") == (expected_start, expected_end)
