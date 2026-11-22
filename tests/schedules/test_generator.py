from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.schedules.domain.generator import (
    InvalidGenerationWindowError,
    ScheduleGenerationLimitError,
    generate_occurrences,
)
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)


def make_regimen(**overrides: object) -> Regimen:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    values: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "medication_name": "Medication X",
        "medication_form": MedicationForm.INJECTION,
        "dose_amount": Decimal("1"),
        "dose_unit": "mg",
        "start_date": date(2026, 10, 20),
        "total_intakes": None,
        "end_date": None,
        "status": RegimenStatus.ACTIVE,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Regimen(**values)  # type: ignore[arg-type]


def utc_boundary(year: int, month: int, day: int, hour: int = 23, minute: int = 59) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_generates_35_injections_every_three_days() -> None:
    regimen = make_regimen(total_intakes=35)
    rule = IntervalScheduleRule(3, (time(10),))

    occurrences = generate_occurrences(
        regimen,
        rule,
        "Europe/Moscow",
        window_end=utc_boundary(2027, 12, 31),
    )

    assert len(occurrences) == 35
    assert occurrences[0].sequence_number == 1
    assert occurrences[0].scheduled_local.date() == date(2026, 10, 20)
    assert occurrences[-1].sequence_number == 35
    assert occurrences[-1].scheduled_local.date() == date(2027, 1, 30)


def test_daily_multiple_times_count_toward_total_intakes() -> None:
    regimen = make_regimen(total_intakes=3)

    occurrences = generate_occurrences(
        regimen,
        DailyScheduleRule((time(21), time(9))),
        "Europe/Moscow",
        window_end=utc_boundary(2026, 10, 25),
    )

    assert [item.scheduled_local.time() for item in occurrences] == [
        time(9),
        time(21),
        time(9),
    ]
    assert [item.sequence_number for item in occurrences] == [1, 2, 3]


def test_weekday_rule_uses_iso_weekdays() -> None:
    regimen = make_regimen(start_date=date(2026, 10, 19))
    rule = WeekdayScheduleRule(frozenset({1, 3, 5}), (time(10),))

    occurrences = generate_occurrences(
        regimen,
        rule,
        "UTC",
        window_end=utc_boundary(2026, 10, 25),
    )

    assert [item.scheduled_local.date() for item in occurrences] == [
        date(2026, 10, 19),
        date(2026, 10, 21),
        date(2026, 10, 23),
    ]


def test_weekly_rule_uses_different_times_on_workdays_and_weekends() -> None:
    regimen = make_regimen(start_date=date(2026, 10, 19))
    rule = WeeklyScheduleRule(
        tuple(
            [(weekday, (time(6, 30),)) for weekday in range(1, 6)]
            + [(weekday, (time(9),)) for weekday in range(6, 8)]
        )
    )

    occurrences = generate_occurrences(
        regimen,
        rule,
        "Europe/Moscow",
        window_end=utc_boundary(2026, 10, 25),
    )

    assert [item.scheduled_local.time() for item in occurrences] == [
        time(6, 30),
        time(6, 30),
        time(6, 30),
        time(6, 30),
        time(6, 30),
        time(9),
        time(9),
    ]


def test_end_date_is_inclusive() -> None:
    regimen = make_regimen(total_intakes=None, end_date=date(2026, 10, 22))

    occurrences = generate_occurrences(
        regimen,
        DailyScheduleRule((time(9),)),
        "UTC",
        window_end=utc_boundary(2026, 10, 30),
    )

    assert [item.scheduled_local.date() for item in occurrences] == [
        date(2026, 10, 20),
        date(2026, 10, 21),
        date(2026, 10, 22),
    ]


def test_window_filter_preserves_global_sequence_numbers() -> None:
    regimen = make_regimen()

    occurrences = generate_occurrences(
        regimen,
        DailyScheduleRule((time(9), time(21))),
        "UTC",
        window_start=datetime(2026, 10, 21, 12, tzinfo=UTC),
        window_end=datetime(2026, 10, 22, 10, tzinfo=UTC),
    )

    assert [item.sequence_number for item in occurrences] == [4, 5]
    assert [item.scheduled_local for item in occurrences] == [
        datetime(2026, 10, 21, 21, tzinfo=UTC),
        datetime(2026, 10, 22, 9, tzinfo=UTC),
    ]


def test_window_can_restart_count_for_new_schedule_version() -> None:
    regimen = make_regimen(total_intakes=2, start_date=date(2026, 10, 21))

    occurrences = generate_occurrences(
        regimen,
        DailyScheduleRule((time(6), time(21))),
        "Europe/Moscow",
        window_start=datetime(2026, 10, 21, 8, tzinfo=UTC),
        window_end=utc_boundary(2026, 10, 22),
        count_before_window=False,
    )

    assert [item.sequence_number for item in occurrences] == [1, 2]
    assert [item.scheduled_local.time() for item in occurrences] == [time(21), time(6)]


def test_spring_dst_gap_shifts_forward_by_gap() -> None:
    regimen = make_regimen(start_date=date(2026, 3, 29), end_date=date(2026, 3, 29))

    occurrence = generate_occurrences(
        regimen,
        DailyScheduleRule((time(2, 30),)),
        "Europe/Berlin",
        window_end=utc_boundary(2026, 3, 29),
    )[0]

    assert occurrence.scheduled_local == datetime(
        2026,
        3,
        29,
        3,
        30,
        tzinfo=ZoneInfo("Europe/Berlin"),
    )
    assert occurrence.scheduled_at == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)


def test_fall_dst_ambiguity_uses_first_fold_without_duplicate() -> None:
    regimen = make_regimen(start_date=date(2026, 10, 25), end_date=date(2026, 10, 25))

    occurrences = generate_occurrences(
        regimen,
        DailyScheduleRule((time(2, 30),)),
        "Europe/Berlin",
        window_end=utc_boundary(2026, 10, 25),
    )

    assert len(occurrences) == 1
    assert occurrences[0].scheduled_local.fold == 0
    assert occurrences[0].scheduled_at == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)


@pytest.mark.parametrize("status", [RegimenStatus.PAUSED, RegimenStatus.COMPLETED])
def test_inactive_regimen_generates_nothing(status: RegimenStatus) -> None:
    assert (
        generate_occurrences(
            make_regimen(status=status),
            DailyScheduleRule((time(9),)),
            "UTC",
            window_end=utc_boundary(2026, 10, 25),
        )
        == ()
    )


def test_window_boundaries_must_be_aware_and_ordered() -> None:
    regimen = make_regimen()
    rule = DailyScheduleRule((time(9),))

    with pytest.raises(InvalidGenerationWindowError):
        generate_occurrences(regimen, rule, "UTC", window_end=datetime(2026, 10, 25))
    with pytest.raises(InvalidGenerationWindowError):
        generate_occurrences(
            regimen,
            rule,
            "UTC",
            window_start=utc_boundary(2026, 10, 26),
            window_end=utc_boundary(2026, 10, 25),
        )


def test_open_ended_generation_has_safety_limit() -> None:
    with pytest.raises(ScheduleGenerationLimitError):
        generate_occurrences(
            make_regimen(),
            DailyScheduleRule((time(9),)),
            "UTC",
            window_end=utc_boundary(2040, 1, 1),
        )
