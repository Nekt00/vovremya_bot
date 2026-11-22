from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.reporting import build_medication_report
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel
from medication_reminder.users.infrastructure.models import UserModel

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_report_counts_course_progress_and_actual_confirmation_time(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    user_id = uuid4()
    other_user_id = uuid4()
    db_session.add_all(
        [
            UserModel(
                id=user_id,
                telegram_user_id=8001,
                timezone="Europe/Moscow",
                reminder_repeat_minutes=30,
                reminders_enabled=True,
            ),
            UserModel(
                id=other_user_id,
                telegram_user_id=8002,
                timezone="Europe/Moscow",
                reminder_repeat_minutes=30,
                reminders_enabled=True,
            ),
        ]
    )
    await db_session.flush()
    regimen_id = uuid4()
    schedule_id = uuid4()
    db_session.add(
        RegimenModel(
            id=regimen_id,
            user_id=user_id,
            medication_name="Укол",
            medication_form="injection",
            dose_amount=Decimal("1"),
            dose_unit="мг",
            start_date=now.date() - timedelta(days=6),
            total_intakes=35,
            end_date=None,
            status="active",
            meal_timing="independent",
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=6),
        )
    )
    await db_session.flush()
    db_session.add(
        ScheduleRuleModel(
            id=schedule_id,
            regimen_id=regimen_id,
            kind="interval",
            payload={"every_days": 3, "times": ["09:00"]},
            timezone="Europe/Moscow",
            version=1,
            active=True,
            created_at=now - timedelta(days=6),
        )
    )
    await db_session.flush()
    statuses = ("taken", "taken", "skipped", "scheduled")
    events = []
    for sequence, event_status in enumerate(statuses, start=1):
        scheduled_at = now - timedelta(days=4 - sequence)
        resolved_at = scheduled_at + timedelta(minutes=17) if event_status != "scheduled" else None
        events.append(
            IntakeEventModel(
                id=uuid4(),
                regimen_id=regimen_id,
                schedule_rule_id=schedule_id,
                sequence_number=sequence,
                scheduled_at=scheduled_at,
                timezone="Europe/Moscow",
                medication_name="Укол",
                medication_form="injection",
                dose_amount=Decimal("1"),
                dose_unit="мг",
                meal_timing="independent",
                status=event_status,
                snoozed_until=None,
                resolved_at=resolved_at,
                created_at=scheduled_at - timedelta(days=1),
                updated_at=resolved_at or scheduled_at,
            )
        )
    db_session.add_all(events)
    await db_session.flush()

    report = await build_medication_report(
        db_session,
        user_id=user_id,
        timezone="Europe/Moscow",
        period="30",
        now=now,
    )

    assert report is not None
    assert report.summary == report.summary.__class__(
        taken=2, missed=1, pending=1, adherence_percent=67
    )
    assert report.courses[0].taken == 2
    assert report.courses[0].remaining_to_target == 33
    taken_event = next(item for item in report.events if item.status == "taken")
    assert taken_event.resolved_at == taken_event.scheduled_at + timedelta(minutes=17)

    other_report = await build_medication_report(
        db_session,
        user_id=other_user_id,
        timezone="Europe/Moscow",
        period="30",
        regimen_id=regimen_id,
        now=now,
    )
    assert other_report is None
