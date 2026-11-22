from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from medication_reminder.regimens.domain.regimen import (
    InvalidRegimenError,
    InvalidStatusTransitionError,
    MedicationForm,
    Regimen,
    RegimenStatus,
)


def make_regimen(**overrides: object) -> Regimen:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    values: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "medication_name": "Vitamin D3",
        "medication_form": MedicationForm.TABLET,
        "dose_amount": Decimal("2"),
        "dose_unit": "tablets",
        "start_date": date(2026, 10, 18),
        "total_intakes": 35,
        "end_date": None,
        "status": RegimenStatus.ACTIVE,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Regimen(**values)  # type: ignore[arg-type]


def test_regimen_normalizes_name_and_dose_unit() -> None:
    regimen = make_regimen(medication_name="  Vitamin   D3 ", dose_unit="  tablets ")

    assert regimen.medication_name == "Vitamin D3"
    assert regimen.dose_unit == "tablets"


@pytest.mark.parametrize("dose_amount", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_regimen_requires_positive_finite_decimal_dose(dose_amount: Decimal) -> None:
    with pytest.raises(InvalidRegimenError, match="finite positive Decimal"):
        make_regimen(dose_amount=dose_amount)


@pytest.mark.parametrize("field", ["medication_name", "dose_unit"])
def test_regimen_requires_non_empty_text(field: str) -> None:
    with pytest.raises(InvalidRegimenError, match="cannot be empty"):
        make_regimen(**{field: "  "})


def test_regimen_rejects_two_end_conditions() -> None:
    with pytest.raises(InvalidRegimenError, match="mutually exclusive"):
        make_regimen(end_date=date(2026, 12, 1))


def test_regimen_accepts_open_ended_condition() -> None:
    regimen = make_regimen(total_intakes=None, end_date=None)

    assert regimen.total_intakes is None
    assert regimen.end_date is None


def test_regimen_rejects_non_positive_total_intakes() -> None:
    with pytest.raises(InvalidRegimenError, match="positive integer"):
        make_regimen(total_intakes=0)


def test_regimen_rejects_end_date_before_start_date() -> None:
    with pytest.raises(InvalidRegimenError, match="before start date"):
        make_regimen(total_intakes=None, end_date=date(2026, 10, 17))


def test_active_regimen_can_be_paused_then_completed() -> None:
    active = make_regimen()
    paused_at = active.updated_at + timedelta(minutes=1)
    completed_at = paused_at + timedelta(minutes=1)

    paused = active.transition_to(RegimenStatus.PAUSED, at=paused_at)
    completed = paused.transition_to(RegimenStatus.COMPLETED, at=completed_at)

    assert paused.status is RegimenStatus.PAUSED
    assert completed.status is RegimenStatus.COMPLETED


def test_paused_regimen_can_be_resumed() -> None:
    paused = make_regimen(status=RegimenStatus.PAUSED)

    active = paused.transition_to(
        RegimenStatus.ACTIVE,
        at=paused.updated_at + timedelta(minutes=1),
    )

    assert active.status is RegimenStatus.ACTIVE


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        (RegimenStatus.ACTIVE, RegimenStatus.ACTIVE),
        (RegimenStatus.PAUSED, RegimenStatus.PAUSED),
        (RegimenStatus.COMPLETED, RegimenStatus.ACTIVE),
        (RegimenStatus.COMPLETED, RegimenStatus.PAUSED),
        (RegimenStatus.COMPLETED, RegimenStatus.COMPLETED),
    ],
)
def test_regimen_rejects_invalid_status_transition(
    initial: RegimenStatus,
    target: RegimenStatus,
) -> None:
    regimen = make_regimen(status=initial)

    with pytest.raises(InvalidStatusTransitionError):
        regimen.transition_to(target, at=regimen.updated_at + timedelta(minutes=1))
