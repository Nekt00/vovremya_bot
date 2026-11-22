from decimal import Decimal

import pytest

from medication_reminder.shared.dosage import format_dose


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("1", "1 таблетка"),
        ("2", "2 таблетки"),
        ("5", "5 таблеток"),
        ("11", "11 таблеток"),
        ("21", "21 таблетка"),
        ("1.5", "1.5 таблетки"),
    ],
)
def test_format_dose_uses_russian_plural_forms(amount: str, expected: str) -> None:
    assert format_dose(Decimal(amount), "таблетка") == expected


def test_format_dose_keeps_unknown_unit() -> None:
    assert format_dose(Decimal("5"), "мл") == "5 мл"
