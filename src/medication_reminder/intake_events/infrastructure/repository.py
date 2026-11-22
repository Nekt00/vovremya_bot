from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.application.repositories import IntakeEventRepository
from medication_reminder.intake_events.domain.event import (
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
)
from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.medication_sets.models import (
    MedicationSetMemberModel,
    MedicationSetModel,
)
from medication_reminder.regimens.domain.regimen import MealTiming, MedicationForm
from medication_reminder.regimens.infrastructure.models import RegimenModel


class SqlAlchemyIntakeEventRepository(IntakeEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, event_id: UUID, user_id: UUID) -> IntakeEvent | None:
        statement = (
            select(IntakeEventModel)
            .join(RegimenModel, IntakeEventModel.regimen_id == RegimenModel.id)
            .where(IntakeEventModel.id == event_id, RegimenModel.user_id == user_id)
        )
        model = (await self._session.scalars(statement)).one_or_none()
        return _to_domain(model) if model is not None else None

    async def next_pending_for_regimen(
        self,
        user_id: UUID,
        regimen_id: UUID,
    ) -> IntakeEvent | None:
        statement = (
            select(IntakeEventModel)
            .join(RegimenModel, IntakeEventModel.regimen_id == RegimenModel.id)
            .where(
                RegimenModel.user_id == user_id,
                IntakeEventModel.regimen_id == regimen_id,
                IntakeEventModel.status.in_(
                    (
                        IntakeEventStatus.SCHEDULED.value,
                        IntakeEventStatus.DUE.value,
                        IntakeEventStatus.SNOOZED.value,
                    )
                ),
            )
            .order_by(IntakeEventModel.scheduled_at, IntakeEventModel.sequence_number)
            .limit(1)
        )
        model = (await self._session.scalars(statement)).one_or_none()
        return _to_domain(model) if model is not None else None

    async def transition(
        self,
        event: IntakeEvent,
        *,
        user_id: UUID,
        expected_status: IntakeEventStatus,
        history: IntakeEventHistory,
    ) -> IntakeEvent | None:
        owned_regimens = select(RegimenModel.id).where(RegimenModel.user_id == user_id)
        statement = (
            update(IntakeEventModel)
            .where(
                IntakeEventModel.id == event.id,
                IntakeEventModel.regimen_id.in_(owned_regimens),
                IntakeEventModel.status == expected_status.value,
            )
            .values(
                status=event.status.value,
                snoozed_until=event.snoozed_until,
                resolved_at=event.resolved_at,
                updated_at=event.updated_at,
            )
            .returning(IntakeEventModel)
            .execution_options(populate_existing=True)
        )
        async with self._session.begin_nested():
            model = (await self._session.scalars(statement)).one_or_none()
            if model is None:
                return None
            self._session.add(
                IntakeEventHistoryModel(
                    id=history.id,
                    event_id=history.event_id,
                    from_status=(
                        history.from_status.value if history.from_status is not None else None
                    ),
                    to_status=history.to_status.value,
                    occurred_at=history.occurred_at,
                    source=history.source.value,
                )
            )
            await self._session.flush()
            return _to_domain(model)

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEvent]:
        statement = (
            select(IntakeEventModel)
            .join(RegimenModel, IntakeEventModel.regimen_id == RegimenModel.id)
            .where(
                RegimenModel.user_id == user_id,
                IntakeEventModel.scheduled_at >= window_start,
                IntakeEventModel.scheduled_at <= window_end,
            )
            .order_by(IntakeEventModel.scheduled_at, IntakeEventModel.sequence_number)
        )
        models = (await self._session.scalars(statement)).all()
        return [_to_domain(model) for model in models]

    async def deadline_for_event(self, event_id: UUID, user_id: UUID) -> datetime | None:
        row = (
            await self._session.execute(
                select(IntakeEventModel, MedicationSetModel)
                .join(RegimenModel, IntakeEventModel.regimen_id == RegimenModel.id)
                .outerjoin(
                    MedicationSetMemberModel,
                    MedicationSetMemberModel.regimen_id == RegimenModel.id,
                )
                .outerjoin(
                    MedicationSetModel,
                    (MedicationSetModel.id == MedicationSetMemberModel.set_id)
                    & MedicationSetModel.active.is_(True),
                )
                .where(IntakeEventModel.id == event_id, RegimenModel.user_id == user_id)
            )
        ).one_or_none()
        if row is None:
            return None
        event, medication_set = row
        timezone = medication_set.timezone if medication_set is not None else event.timezone
        zone = ZoneInfo(timezone)
        local_date = _as_utc(event.scheduled_at).astimezone(zone).date()
        if medication_set is not None:
            return datetime.combine(local_date, medication_set.window_end, zone).astimezone(UTC)
        return datetime.combine(
            local_date + timedelta(days=1),
            time.min,
            zone,
        ).astimezone(UTC)

    async def list_details_for_user(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEventDetails]:
        statement = (
            select(IntakeEventModel)
            .join(RegimenModel, IntakeEventModel.regimen_id == RegimenModel.id)
            .where(
                RegimenModel.user_id == user_id,
                IntakeEventModel.scheduled_at >= window_start,
                IntakeEventModel.scheduled_at < window_end,
            )
            .order_by(IntakeEventModel.scheduled_at, IntakeEventModel.sequence_number)
        )
        models = (await self._session.scalars(statement)).all()
        return [
            IntakeEventDetails(
                event=_to_domain(event_model),
                medication_name=event_model.medication_name,
                medication_form=MedicationForm(event_model.medication_form),
                dose_amount=event_model.dose_amount,
                dose_unit=event_model.dose_unit,
                meal_timing=MealTiming(event_model.meal_timing),
            )
            for event_model in models
        ]


def _to_domain(model: IntakeEventModel) -> IntakeEvent:
    return IntakeEvent(
        id=model.id,
        regimen_id=model.regimen_id,
        schedule_rule_id=model.schedule_rule_id,
        sequence_number=model.sequence_number,
        scheduled_at=_as_utc(model.scheduled_at),
        timezone=model.timezone,
        status=IntakeEventStatus(model.status),
        snoozed_until=_as_utc(model.snoozed_until) if model.snoozed_until is not None else None,
        resolved_at=_as_utc(model.resolved_at) if model.resolved_at is not None else None,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Database returned a timestamp without timezone information")
    return value.astimezone(UTC)
