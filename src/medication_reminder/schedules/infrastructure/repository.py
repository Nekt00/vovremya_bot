from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventHistory
from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.regimens.domain.regimen import Regimen
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel
from medication_reminder.schedules.infrastructure.serialization import (
    JsonObject,
    deserialize_schedule_rule,
    serialize_schedule_rule,
)


class SqlAlchemyScheduleMaterializationStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def materialize(
        self,
        schedule: StoredScheduleRule,
        events: tuple[IntakeEvent, ...],
        histories: tuple[IntakeEventHistory, ...],
        *,
        regimen: Regimen,
    ) -> None:
        kind, payload = serialize_schedule_rule(schedule.rule)
        schedule_model = ScheduleRuleModel(
            id=schedule.id,
            regimen_id=schedule.regimen_id,
            kind=kind,
            payload=payload,
            timezone=schedule.timezone,
            version=schedule.version,
            active=schedule.active,
            created_at=schedule.created_at,
        )
        event_models = [_event_model(event, regimen) for event in events]
        history_models = [_history_model(history) for history in histories]
        async with self._session.begin_nested():
            self._session.add(schedule_model)
            await self._session.flush()
            self._session.add_all(event_models)
            await self._session.flush()
            self._session.add_all(history_models)
            await self._session.flush()

    async def get_active(self, regimen_id: UUID) -> StoredScheduleRule | None:
        statement = select(ScheduleRuleModel).where(
            ScheduleRuleModel.regimen_id == regimen_id,
            ScheduleRuleModel.active.is_(True),
        )
        model = (await self._session.scalars(statement)).one_or_none()
        return _schedule_to_domain(model) if model is not None else None


def _event_model(event: IntakeEvent, regimen: Regimen) -> IntakeEventModel:
    return IntakeEventModel(
        id=event.id,
        regimen_id=event.regimen_id,
        schedule_rule_id=event.schedule_rule_id,
        sequence_number=event.sequence_number,
        scheduled_at=event.scheduled_at,
        timezone=event.timezone,
        medication_name=regimen.medication_name,
        medication_form=regimen.medication_form.value,
        dose_amount=regimen.dose_amount,
        dose_unit=regimen.dose_unit,
        meal_timing=regimen.meal_timing.value,
        status=event.status.value,
        snoozed_until=event.snoozed_until,
        resolved_at=event.resolved_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def _history_model(history: IntakeEventHistory) -> IntakeEventHistoryModel:
    return IntakeEventHistoryModel(
        id=history.id,
        event_id=history.event_id,
        from_status=history.from_status.value if history.from_status is not None else None,
        to_status=history.to_status.value,
        occurred_at=history.occurred_at,
        source=history.source.value,
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
