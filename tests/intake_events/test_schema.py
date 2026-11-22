from typing import cast

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel


def test_intake_event_rule_reference_includes_regimen() -> None:
    table = cast(Table, IntakeEventModel.__table__)
    foreign_keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    composite = next(
        constraint
        for constraint in foreign_keys
        if constraint.name == "fk_intake_events_schedule_rule_regimen"
    )

    assert [column.name for column in composite.columns] == ["schedule_rule_id", "regimen_id"]
    assert [element.target_fullname for element in composite.elements] == [
        "schedule_rules.id",
        "schedule_rules.regimen_id",
    ]
    assert composite.ondelete == "CASCADE"
    assert not any(
        [column.name for column in constraint.columns] == ["schedule_rule_id"]
        for constraint in foreign_keys
    )


def test_schedule_rule_exposes_unique_composite_reference_target() -> None:
    table = cast(Table, ScheduleRuleModel.__table__)
    unique_constraints = [
        constraint for constraint in table.constraints if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        constraint.name == "uq_schedule_rules_id_regimen"
        and [column.name for column in constraint.columns] == ["id", "regimen_id"]
        for constraint in unique_constraints
    )


def test_intake_event_constrains_meal_timing_snapshot() -> None:
    table = cast(Table, IntakeEventModel.__table__)

    assert "meal_timing" in table.columns
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_intake_events_meal_timing"
        for constraint in table.constraints
    )
