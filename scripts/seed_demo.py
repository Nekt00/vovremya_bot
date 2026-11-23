import asyncio
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from medication_reminder.intake_events.domain.event import EventSource, IntakeEventStatus
from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.regimens.application.use_cases import (
    CreateRegimen,
    CreateRegimenCommand,
)
from medication_reminder.regimens.domain.regimen import MealTiming, MedicationForm
from medication_reminder.regimens.infrastructure.repository import SqlAlchemyRegimenRepository
from medication_reminder.schedules.application.use_cases import MaterializeSchedule
from medication_reminder.schedules.domain.rules import DailyScheduleRule
from medication_reminder.schedules.infrastructure.repository import (
    SqlAlchemyScheduleMaterializationStore,
)
from medication_reminder.shared.config import get_settings
from medication_reminder.shared.database import create_database_engine, create_session_factory
from medication_reminder.users.infrastructure.models import UserModel

_TIMEZONE = "Europe/Moscow"
_TELEGRAM_USER_ID = 100_000_001


async def main() -> None:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    now = datetime.now(UTC)
    zone = ZoneInfo(_TIMEZONE)
    today = now.astimezone(zone).date()
    window_start = datetime.combine(today - timedelta(days=7), time.min, zone).astimezone(UTC)
    window_end = datetime.combine(today + timedelta(days=7), time.min, zone).astimezone(UTC)

    try:
        async with session_factory() as session, session.begin():
            existing_user = await session.scalar(select(UserModel.id).limit(1))
            if existing_user is not None:
                return

            user_id = uuid4()
            session.add(
                UserModel(
                    id=user_id,
                    telegram_user_id=_TELEGRAM_USER_ID,
                    timezone=_TIMEZONE,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()

            regimens = SqlAlchemyRegimenRepository(session)
            schedules = SqlAlchemyScheduleMaterializationStore(session)
            create_regimen = CreateRegimen(regimens, clock=lambda: now)
            materialize = MaterializeSchedule(schedules, clock=lambda: now)

            metformin = await create_regimen(
                CreateRegimenCommand(
                    user_id=user_id,
                    medication_name="Метформин",
                    medication_form=MedicationForm.TABLET,
                    dose_amount=Decimal("500"),
                    dose_unit="мг",
                    start_date=today - timedelta(days=7),
                    meal_timing=MealTiming.AFTER,
                )
            )
            vitamin_d = await create_regimen(
                CreateRegimenCommand(
                    user_id=user_id,
                    medication_name="Витамин D",
                    medication_form=MedicationForm.CAPSULE,
                    dose_amount=Decimal("1000"),
                    dose_unit="ед.",
                    start_date=today - timedelta(days=7),
                )
            )

            await materialize(
                metformin,
                DailyScheduleRule((time(8), time(20))),
                _TIMEZONE,
                window_start=window_start,
                window_end=window_end,
            )
            await materialize(
                vitamin_d,
                DailyScheduleRule((time(13),)),
                _TIMEZONE,
                window_start=window_start,
                window_end=window_end,
            )

            previous = await session.scalar(
                select(IntakeEventModel)
                .where(IntakeEventModel.scheduled_at < now)
                .order_by(IntakeEventModel.scheduled_at.desc())
                .limit(1)
            )
            assert previous is not None
            previous.status = IntakeEventStatus.TAKEN.value
            previous.resolved_at = now
            previous.updated_at = now
            session.add(
                IntakeEventHistoryModel(
                    id=uuid4(),
                    event_id=previous.id,
                    from_status=IntakeEventStatus.SCHEDULED.value,
                    to_status=IntakeEventStatus.TAKEN.value,
                    occurred_at=now,
                    source=EventSource.USER.value,
                )
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
