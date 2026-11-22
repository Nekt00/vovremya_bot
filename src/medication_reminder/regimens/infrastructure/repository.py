from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.domain.event import IntakeEventStatus
from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.regimens.domain.regimen import (
    MealTiming,
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.regimens.infrastructure.models import RegimenModel


class SqlAlchemyRegimenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, regimen: Regimen) -> Regimen:
        self._session.add(
            RegimenModel(
                id=regimen.id,
                user_id=regimen.user_id,
                medication_name=regimen.medication_name,
                medication_form=regimen.medication_form.value,
                dose_amount=regimen.dose_amount,
                dose_unit=regimen.dose_unit,
                start_date=regimen.start_date,
                total_intakes=regimen.total_intakes,
                end_date=regimen.end_date,
                status=regimen.status.value,
                created_at=regimen.created_at,
                updated_at=regimen.updated_at,
                meal_timing=regimen.meal_timing.value,
            )
        )
        await self._session.flush()
        return regimen

    async def list_for_user(self, user_id: UUID) -> list[Regimen]:
        statement = (
            select(RegimenModel)
            .where(RegimenModel.user_id == user_id)
            .order_by(RegimenModel.created_at.desc(), RegimenModel.id)
        )
        models = (await self._session.scalars(statement)).all()
        return [_to_domain(model) for model in models]

    async def get_for_user(self, regimen_id: UUID, user_id: UUID) -> Regimen | None:
        statement = select(RegimenModel).where(
            RegimenModel.id == regimen_id,
            RegimenModel.user_id == user_id,
        )
        model = (await self._session.scalars(statement)).one_or_none()
        return _to_domain(model) if model is not None else None

    async def update_status(
        self,
        regimen_id: UUID,
        user_id: UUID,
        *,
        expected_status: RegimenStatus,
        target_status: RegimenStatus,
        updated_at: datetime,
        cancel_outstanding: bool = False,
        cancel_overdue: bool = False,
    ) -> Regimen | None:
        async with self._session.begin_nested():
            statement = (
                update(RegimenModel)
                .where(
                    RegimenModel.id == regimen_id,
                    RegimenModel.user_id == user_id,
                    RegimenModel.status == expected_status.value,
                )
                .values(status=target_status.value, updated_at=updated_at)
                .returning(RegimenModel)
            )
            model = (await self._session.scalars(statement)).one_or_none()
            if model is None:
                return None
            if cancel_outstanding:
                await self._cancel_outstanding_events(regimen_id, updated_at)
            elif cancel_overdue:
                await self._cancel_outstanding_events(
                    regimen_id,
                    updated_at,
                    scheduled_before=updated_at,
                )
            await self._session.flush()
            return _to_domain(model)

    async def _cancel_outstanding_events(
        self,
        regimen_id: UUID,
        occurred_at: datetime,
        *,
        scheduled_before: datetime | None = None,
    ) -> None:
        statuses = (
            IntakeEventStatus.SCHEDULED.value,
            IntakeEventStatus.DUE.value,
            IntakeEventStatus.SNOOZED.value,
        )
        conditions = [
            IntakeEventModel.regimen_id == regimen_id,
            IntakeEventModel.status.in_(statuses),
        ]
        if scheduled_before is not None:
            conditions.append(IntakeEventModel.scheduled_at <= scheduled_before)
        statement = select(IntakeEventModel).where(*conditions).with_for_update()
        events = (await self._session.scalars(statement)).all()
        for event in events:
            previous_status = event.status
            event.status = IntakeEventStatus.CANCELLED.value
            event.snoozed_until = None
            event.resolved_at = occurred_at
            event.updated_at = occurred_at
            self._session.add(
                IntakeEventHistoryModel(
                    id=uuid4(),
                    event_id=event.id,
                    from_status=previous_status,
                    to_status=IntakeEventStatus.CANCELLED.value,
                    occurred_at=occurred_at,
                    source="user",
                )
            )

    async def delete_for_user(self, regimen_id: UUID, user_id: UUID) -> bool:
        result = await self._session.scalars(
            delete(RegimenModel)
            .where(RegimenModel.id == regimen_id, RegimenModel.user_id == user_id)
            .returning(RegimenModel.id)
        )
        return result.one_or_none() is not None


def _to_domain(model: RegimenModel) -> Regimen:
    return Regimen(
        id=model.id,
        user_id=model.user_id,
        medication_name=model.medication_name,
        medication_form=MedicationForm(model.medication_form),
        dose_amount=model.dose_amount,
        dose_unit=model.dose_unit,
        start_date=model.start_date,
        total_intakes=model.total_intakes,
        end_date=model.end_date,
        status=RegimenStatus(model.status),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
        meal_timing=MealTiming(model.meal_timing),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Database returned a timestamp without timezone information")
    return value.astimezone(UTC)
