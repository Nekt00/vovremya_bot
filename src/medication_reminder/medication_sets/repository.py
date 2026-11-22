from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.families.models import FamilyRegimenAssignmentModel
from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.medication_sets.domain import MedicationSet, MedicationSetDetails
from medication_reminder.medication_sets.models import (
    MedicationSetMemberModel,
    MedicationSetModel,
)
from medication_reminder.regimens.domain.regimen import (
    MealTiming,
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.regimens.infrastructure.models import RegimenModel


class SqlAlchemyMedicationSetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, medication_set: MedicationSet, regimen_ids: tuple[UUID, ...]) -> bool:
        available = set(
            (
                await self._session.scalars(
                    select(RegimenModel.id).where(
                        RegimenModel.id.in_(regimen_ids),
                        RegimenModel.user_id == medication_set.user_id,
                        RegimenModel.status == RegimenStatus.ACTIVE.value,
                    )
                )
            ).all()
        )
        if available != set(regimen_ids):
            return False
        try:
            async with self._session.begin_nested():
                self._session.add(
                    MedicationSetModel(
                        id=medication_set.id,
                        user_id=medication_set.user_id,
                        name=medication_set.name,
                        window_start=medication_set.window_start,
                        window_end=medication_set.window_end,
                        timezone=medication_set.timezone,
                        active=medication_set.active,
                        created_at=medication_set.created_at,
                        updated_at=medication_set.updated_at,
                    )
                )
                await self._session.flush()
                self._session.add_all(
                    MedicationSetMemberModel(
                        set_id=medication_set.id,
                        regimen_id=regimen_id,
                        created_at=medication_set.created_at,
                    )
                    for regimen_id in regimen_ids
                )
                await self._session.flush()
        except IntegrityError:
            return False
        return True

    async def list_for_user(self, user_id: UUID) -> list[MedicationSetDetails]:
        sets = list(
            (
                await self._session.scalars(
                    select(MedicationSetModel)
                    .where(MedicationSetModel.user_id == user_id)
                    .order_by(MedicationSetModel.window_start, MedicationSetModel.created_at)
                )
            ).all()
        )
        if not sets:
            return []
        rows = (
            await self._session.execute(
                select(MedicationSetMemberModel.set_id, RegimenModel)
                .join(RegimenModel, RegimenModel.id == MedicationSetMemberModel.regimen_id)
                .where(MedicationSetMemberModel.set_id.in_(item.id for item in sets))
                .order_by(RegimenModel.medication_name)
            )
        ).all()
        regimens_by_set: dict[UUID, list[Regimen]] = {item.id: [] for item in sets}
        for set_id, regimen in rows:
            regimens_by_set[set_id].append(_regimen(regimen))
        return [
            MedicationSetDetails(_medication_set(item), tuple(regimens_by_set[item.id]))
            for item in sets
        ]

    async def get_for_user(self, user_id: UUID, set_id: UUID) -> MedicationSetDetails | None:
        medication_set = (
            await self._session.scalars(
                select(MedicationSetModel).where(
                    MedicationSetModel.id == set_id,
                    MedicationSetModel.user_id == user_id,
                )
            )
        ).one_or_none()
        if medication_set is None:
            return None
        regimens = (
            await self._session.scalars(
                select(RegimenModel)
                .join(
                    MedicationSetMemberModel,
                    MedicationSetMemberModel.regimen_id == RegimenModel.id,
                )
                .where(MedicationSetMemberModel.set_id == set_id)
                .order_by(RegimenModel.medication_name)
            )
        ).all()
        return MedicationSetDetails(
            _medication_set(medication_set), tuple(_regimen(item) for item in regimens)
        )

    async def update(
        self,
        medication_set: MedicationSet,
        regimen_ids: tuple[UUID, ...],
    ) -> bool:
        has_delegated_member = await self._session.scalar(
            select(
                exists(
                    select(MedicationSetMemberModel.regimen_id)
                    .join(
                        FamilyRegimenAssignmentModel,
                        FamilyRegimenAssignmentModel.regimen_id
                        == MedicationSetMemberModel.regimen_id,
                    )
                    .where(MedicationSetMemberModel.set_id == medication_set.id)
                )
            )
        )
        if has_delegated_member:
            return False
        current_members = set(
            (
                await self._session.scalars(
                    select(MedicationSetMemberModel.regimen_id).where(
                        MedicationSetMemberModel.set_id == medication_set.id
                    )
                )
            ).all()
        )
        allowed = set(
            (
                await self._session.scalars(
                    select(RegimenModel.id).where(
                        RegimenModel.id.in_(regimen_ids),
                        RegimenModel.user_id == medication_set.user_id,
                        (RegimenModel.status == RegimenStatus.ACTIVE.value)
                        | RegimenModel.id.in_(current_members),
                    )
                )
            ).all()
        )
        if allowed != set(regimen_ids):
            return False
        try:
            async with self._session.begin_nested():
                model = (
                    await self._session.scalars(
                        select(MedicationSetModel)
                        .where(
                            MedicationSetModel.id == medication_set.id,
                            MedicationSetModel.user_id == medication_set.user_id,
                        )
                        .with_for_update()
                    )
                ).one_or_none()
                if model is None:
                    return False
                model.name = medication_set.name
                model.window_start = medication_set.window_start
                model.window_end = medication_set.window_end
                model.updated_at = medication_set.updated_at
                await self._session.execute(
                    delete(MedicationSetMemberModel).where(
                        MedicationSetMemberModel.set_id == medication_set.id
                    )
                )
                self._session.add_all(
                    MedicationSetMemberModel(
                        set_id=medication_set.id,
                        regimen_id=regimen_id,
                        created_at=medication_set.updated_at,
                    )
                    for regimen_id in regimen_ids
                )
                await self._session.flush()
        except IntegrityError:
            return False
        return True

    async def delete(self, user_id: UUID, set_id: UUID) -> bool:
        deleted = await self._session.scalars(
            delete(MedicationSetModel)
            .where(
                MedicationSetModel.id == set_id,
                MedicationSetModel.user_id == user_id,
                ~exists(
                    select(MedicationSetMemberModel.regimen_id)
                    .join(
                        FamilyRegimenAssignmentModel,
                        FamilyRegimenAssignmentModel.regimen_id
                        == MedicationSetMemberModel.regimen_id,
                    )
                    .where(MedicationSetMemberModel.set_id == set_id)
                ),
            )
            .returning(MedicationSetModel.id)
        )
        return deleted.one_or_none() is not None

    async def add_member(self, user_id: UUID, set_id: UUID, regimen_id: UUID) -> bool:
        valid = (
            await self._session.execute(
                select(MedicationSetModel.id, RegimenModel.id)
                .join(RegimenModel, RegimenModel.user_id == MedicationSetModel.user_id)
                .where(
                    MedicationSetModel.id == set_id,
                    MedicationSetModel.user_id == user_id,
                    MedicationSetModel.active.is_(True),
                    RegimenModel.id == regimen_id,
                    RegimenModel.status == RegimenStatus.ACTIVE.value,
                )
            )
        ).one_or_none()
        if valid is None:
            return False
        try:
            async with self._session.begin_nested():
                self._session.add(MedicationSetMemberModel(set_id=set_id, regimen_id=regimen_id))
                await self._session.flush()
        except IntegrityError:
            return False
        return True

    async def take_all(
        self,
        user_id: UUID,
        set_id: UUID,
        local_date: date,
        *,
        occurred_at: datetime,
    ) -> int:
        medication_set = (
            await self._session.scalars(
                select(MedicationSetModel).where(
                    MedicationSetModel.id == set_id,
                    MedicationSetModel.user_id == user_id,
                    MedicationSetModel.active.is_(True),
                )
            )
        ).one_or_none()
        if medication_set is None:
            return 0
        zone = ZoneInfo(medication_set.timezone)
        window_start = datetime.combine(local_date, medication_set.window_start, zone).astimezone(
            UTC
        )
        window_end = datetime.combine(local_date, medication_set.window_end, zone).astimezone(UTC)
        if not window_start <= occurred_at < window_end:
            return 0
        events = list(
            (
                await self._session.scalars(
                    select(IntakeEventModel)
                    .join(
                        MedicationSetMemberModel,
                        MedicationSetMemberModel.regimen_id == IntakeEventModel.regimen_id,
                    )
                    .join(RegimenModel, RegimenModel.id == IntakeEventModel.regimen_id)
                    .where(
                        MedicationSetMemberModel.set_id == set_id,
                        RegimenModel.status == RegimenStatus.ACTIVE.value,
                        IntakeEventModel.scheduled_at >= window_start,
                        IntakeEventModel.scheduled_at < window_end,
                        IntakeEventModel.scheduled_at <= occurred_at,
                        IntakeEventModel.status.in_(("scheduled", "due", "snoozed")),
                    )
                    .with_for_update()
                )
            ).all()
        )
        for event in events:
            previous = event.status
            event.status = "taken"
            event.snoozed_until = None
            event.resolved_at = occurred_at
            event.updated_at = occurred_at
            self._session.add(
                IntakeEventHistoryModel(
                    id=uuid4(),
                    event_id=event.id,
                    from_status=previous,
                    to_status="taken",
                    occurred_at=occurred_at,
                    source="user",
                )
            )
        await self._session.flush()
        return len(events)


def _medication_set(model: MedicationSetModel) -> MedicationSet:
    return MedicationSet(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        window_start=model.window_start,
        window_end=model.window_end,
        timezone=model.timezone,
        active=model.active,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _regimen(model: RegimenModel) -> Regimen:
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
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
        meal_timing=MealTiming(model.meal_timing),
    )


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)
