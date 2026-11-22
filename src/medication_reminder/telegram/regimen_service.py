from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID

from medication_reminder.families.service import FamilyAccessError, FamilyService
from medication_reminder.intake_events.domain.event import IntakeEvent
from medication_reminder.regimens.application.repositories import (
    RegimenDeletionRepository,
    RegimenRepository,
)
from medication_reminder.regimens.application.revisions import (
    ReviseRegimen,
    ReviseRegimenCommand,
)
from medication_reminder.regimens.application.use_cases import (
    ChangeRegimenStatus,
    GetUserRegimen,
    ListUserRegimens,
)
from medication_reminder.regimens.domain.regimen import MealTiming, Regimen, RegimenStatus
from medication_reminder.schedules.application.repositories import ScheduleMaterializationStore
from medication_reminder.schedules.domain.rules import ScheduleRule
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.telegram.clock import Clock
from medication_reminder.users.application.repositories import UserRepository
from medication_reminder.users.application.use_cases import GetOrCreateUser


@dataclass(frozen=True, slots=True)
class RegimenDetails:
    regimen: Regimen
    schedule: StoredScheduleRule | None
    next_event: IntakeEvent | None = None
    can_manage: bool = True
    family_assignment: bool = False


class NextIntakeRepository(Protocol):
    async def next_pending_for_regimen(
        self,
        user_id: UUID,
        regimen_id: UUID,
    ) -> IntakeEvent | None: ...


class TelegramRegimenService:
    def __init__(
        self,
        user_repository: UserRepository,
        regimen_repository: RegimenRepository,
        schedule_store: ScheduleMaterializationStore,
        next_intake_repository: NextIntakeRepository,
        revise_regimen: ReviseRegimen,
        family_service: FamilyService | None = None,
        *,
        clock: Clock,
    ) -> None:
        self._get_user = GetOrCreateUser(user_repository)
        self._delete_repository = cast(RegimenDeletionRepository, regimen_repository)
        self._list = ListUserRegimens(regimen_repository)
        self._get = GetUserRegimen(regimen_repository)
        self._change_status = ChangeRegimenStatus(regimen_repository, clock=clock)
        self._schedule_store = schedule_store
        self._next_intake_repository = next_intake_repository
        self._revise = revise_regimen
        self._family_service = family_service
        self._clock = clock

    async def list_for_user(self, telegram_user_id: int) -> list[Regimen]:
        user = await self._get_user(telegram_user_id)
        return await self._list(user.id)

    async def details(self, telegram_user_id: int, regimen_id: UUID) -> RegimenDetails:
        actor = await self._get_user(telegram_user_id)
        target_user_id = actor.id
        can_manage = True
        family_assignment = False
        if self._family_service is not None:
            try:
                target_user_id, family_assignment = await self._family_service.management_user_id(
                    telegram_user_id, regimen_id
                )
                if not family_assignment:
                    can_manage = await self._family_service.can_manage_personal_regimens(
                        telegram_user_id
                    )
            except FamilyAccessError:
                can_manage = False
                family_assignment = True
        regimen = await self._get(target_user_id, regimen_id)
        schedule = await self._schedule_store.get_active(regimen.id)
        next_event = (
            await self._next_intake_repository.next_pending_for_regimen(target_user_id, regimen.id)
            if regimen.status is RegimenStatus.ACTIVE
            else None
        )
        return RegimenDetails(
            regimen,
            schedule,
            next_event,
            can_manage=can_manage,
            family_assignment=family_assignment,
        )

    async def revise(
        self,
        telegram_user_id: int,
        regimen_id: UUID,
        *,
        dose_amount: Decimal | None,
        rule: ScheduleRule | None,
        meal_timing: MealTiming | None = None,
        remaining_intakes: int | None = None,
        end_date: date | None = None,
    ) -> RegimenDetails:
        user_id = await self._management_user_id(telegram_user_id, regimen_id)
        result = await self._revise(
            ReviseRegimenCommand(
                user_id=user_id,
                regimen_id=regimen_id,
                effective_at=self._clock(),
                dose_amount=dose_amount,
                meal_timing=meal_timing,
                rule=rule,
                remaining_intakes=remaining_intakes,
                end_date=end_date,
            )
        )
        next_event = await self._next_intake_repository.next_pending_for_regimen(
            user_id, result.regimen.id
        )
        return RegimenDetails(result.regimen, result.schedule, next_event)

    async def change_status(
        self,
        telegram_user_id: int,
        regimen_id: UUID,
        target: RegimenStatus,
    ) -> RegimenDetails:
        user_id = await self._management_user_id(telegram_user_id, regimen_id)
        regimen = await self._change_status(user_id, regimen_id, target)
        schedule = await self._schedule_store.get_active(regimen.id)
        next_event = (
            await self._next_intake_repository.next_pending_for_regimen(user_id, regimen.id)
            if regimen.status is RegimenStatus.ACTIVE
            else None
        )
        return RegimenDetails(
            regimen,
            schedule,
            next_event,
            can_manage=True,
            family_assignment=user_id != (await self._get_user(telegram_user_id)).id,
        )

    async def delete(self, telegram_user_id: int, regimen_id: UUID) -> bool:
        user_id = await self._management_user_id(telegram_user_id, regimen_id)
        return await self._delete_repository.delete_for_user(regimen_id, user_id)

    async def _management_user_id(self, telegram_user_id: int, regimen_id: UUID) -> UUID:
        if self._family_service is None:
            return (await self._get_user(telegram_user_id)).id
        user_id, _family_assignment = await self._family_service.management_user_id(
            telegram_user_id, regimen_id
        )
        if not _family_assignment:
            await self._family_service.ensure_can_manage_personal_regimens(telegram_user_id)
        return user_id
