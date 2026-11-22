from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.domain.event import (
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
)
from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.regimens.application.revisions import (
    RegimenRevisionConflictError,
    RevisionContext,
)
from medication_reminder.regimens.domain.regimen import (
    MealTiming,
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel
from medication_reminder.schedules.infrastructure.repository import (
    SqlAlchemyScheduleMaterializationStore,
)
from medication_reminder.schedules.infrastructure.serialization import (
    JsonObject,
    deserialize_schedule_rule,
)


class SqlAlchemyRegimenRevisionStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_context(
        self,
        user_id: UUID,
        regimen_id: UUID,
        *,
        effective_at: datetime,
    ) -> RevisionContext | None:
        regimen_statement = select(RegimenModel).where(
            RegimenModel.id == regimen_id,
            RegimenModel.user_id == user_id,
            RegimenModel.status == RegimenStatus.ACTIVE.value,
        )
        regimen_model = (await self._session.scalars(regimen_statement)).one_or_none()
        if regimen_model is None:
            return None
        schedule_statement = select(ScheduleRuleModel).where(
            ScheduleRuleModel.regimen_id == regimen_model.id,
            ScheduleRuleModel.active.is_(True),
        )
        schedule_model = (await self._session.scalars(schedule_statement)).one_or_none()
        if schedule_model is None:
            return None
        count_statement = select(func.count(IntakeEventModel.id)).where(
            IntakeEventModel.regimen_id == regimen_model.id,
            IntakeEventModel.status == IntakeEventStatus.SCHEDULED.value,
            IntakeEventModel.scheduled_at > effective_at,
        )
        replaceable_count = int((await self._session.scalar(count_statement)) or 0)
        resolved_statement = select(func.count(IntakeEventModel.id)).where(
            IntakeEventModel.regimen_id == regimen_model.id,
            IntakeEventModel.status.in_(
                (
                    IntakeEventStatus.TAKEN.value,
                    IntakeEventStatus.SKIPPED.value,
                    IntakeEventStatus.MISSED.value,
                )
            ),
        )
        pending_statement = select(func.count(IntakeEventModel.id)).where(
            IntakeEventModel.regimen_id == regimen_model.id,
            (
                IntakeEventModel.status.in_(
                    (IntakeEventStatus.DUE.value, IntakeEventStatus.SNOOZED.value)
                )
                | (
                    (IntakeEventModel.status == IntakeEventStatus.SCHEDULED.value)
                    & (IntakeEventModel.scheduled_at <= effective_at)
                )
            ),
        )
        resolved_count = int((await self._session.scalar(resolved_statement)) or 0)
        pending_count = int((await self._session.scalar(pending_statement)) or 0)
        return RevisionContext(
            regimen=_regimen_to_domain(regimen_model),
            active_schedule=_schedule_to_domain(schedule_model),
            replaceable_count=replaceable_count,
            resolved_count=resolved_count,
            pending_count=pending_count,
        )

    async def apply_revision(
        self,
        context: RevisionContext,
        revised_regimen: Regimen,
        schedule: StoredScheduleRule,
        events: tuple[IntakeEvent, ...],
        histories: tuple[IntakeEventHistory, ...],
        *,
        effective_at: datetime,
    ) -> None:
        async with self._session.begin_nested():
            regimen_model = (
                await self._session.scalars(
                    select(RegimenModel)
                    .where(
                        RegimenModel.id == context.regimen.id,
                        RegimenModel.user_id == context.regimen.user_id,
                        RegimenModel.status == RegimenStatus.ACTIVE.value,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            schedule_model = (
                await self._session.scalars(
                    select(ScheduleRuleModel)
                    .where(
                        ScheduleRuleModel.id == context.active_schedule.id,
                        ScheduleRuleModel.active.is_(True),
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if regimen_model is None or schedule_model is None:
                raise RegimenRevisionConflictError("Regimen was changed concurrently")

            all_event_models = list(
                (
                    await self._session.scalars(
                        select(IntakeEventModel)
                        .where(
                            IntakeEventModel.regimen_id == regimen_model.id,
                        )
                        .with_for_update()
                    )
                ).all()
            )
            event_models = [
                event
                for event in all_event_models
                if event.status == IntakeEventStatus.SCHEDULED.value
                and event.scheduled_at > effective_at
            ]
            resolved_count = sum(
                event.status
                in {
                    IntakeEventStatus.TAKEN.value,
                    IntakeEventStatus.SKIPPED.value,
                    IntakeEventStatus.MISSED.value,
                }
                for event in all_event_models
            )
            pending_count = sum(
                event.status in {IntakeEventStatus.DUE.value, IntakeEventStatus.SNOOZED.value}
                or (
                    event.status == IntakeEventStatus.SCHEDULED.value
                    and event.scheduled_at <= effective_at
                )
                for event in all_event_models
            )
            if len(event_models) != context.replaceable_count:
                raise RegimenRevisionConflictError("Future events were changed concurrently")
            if resolved_count != context.resolved_count or pending_count != context.pending_count:
                raise RegimenRevisionConflictError("Intake events were changed concurrently")

            regimen_model.dose_amount = revised_regimen.dose_amount
            regimen_model.meal_timing = revised_regimen.meal_timing.value
            regimen_model.total_intakes = revised_regimen.total_intakes
            regimen_model.end_date = revised_regimen.end_date
            regimen_model.updated_at = revised_regimen.updated_at
            schedule_model.active = False
            for event in event_models:
                event.status = IntakeEventStatus.CANCELLED.value
                event.resolved_at = revised_regimen.updated_at
                event.updated_at = revised_regimen.updated_at
                self._session.add(
                    IntakeEventHistoryModel(
                        id=uuid4(),
                        event_id=event.id,
                        from_status=IntakeEventStatus.SCHEDULED.value,
                        to_status=IntakeEventStatus.CANCELLED.value,
                        occurred_at=revised_regimen.updated_at,
                        source="user",
                    )
                )
            await self._session.flush()
            await SqlAlchemyScheduleMaterializationStore(self._session).materialize(
                schedule,
                events,
                histories,
                regimen=revised_regimen,
            )


def _regimen_to_domain(model: RegimenModel) -> Regimen:
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


def _schedule_to_domain(model: ScheduleRuleModel) -> StoredScheduleRule:
    return StoredScheduleRule(
        id=model.id,
        regimen_id=model.regimen_id,
        rule=deserialize_schedule_rule(model.kind, cast(JsonObject, model.payload)),
        timezone=model.timezone,
        version=model.version,
        active=model.active,
        created_at=_as_utc(model.created_at),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Database returned a timestamp without timezone information")
    return value.astimezone(UTC)
