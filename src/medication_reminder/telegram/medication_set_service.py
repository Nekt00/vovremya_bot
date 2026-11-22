from __future__ import annotations

import builtins
from datetime import date, time
from uuid import UUID

from medication_reminder.families.service import FamilyService
from medication_reminder.medication_sets.application import (
    CreateMedicationSet,
    CreateMedicationSetCommand,
    DeleteMedicationSet,
    GetMedicationSet,
    ListMedicationSets,
    TakeMedicationSet,
    UpdateMedicationSet,
    UpdateMedicationSetCommand,
)
from medication_reminder.medication_sets.domain import MedicationSet, MedicationSetDetails
from medication_reminder.regimens.application.use_cases import ListUserRegimens
from medication_reminder.regimens.domain.regimen import Regimen, RegimenStatus
from medication_reminder.users.application.use_cases import GetOrCreateUser


class TelegramMedicationSetService:
    def __init__(
        self,
        get_user: GetOrCreateUser,
        list_regimens: ListUserRegimens,
        create_set: CreateMedicationSet,
        list_sets: ListMedicationSets,
        take_set: TakeMedicationSet,
        get_set: GetMedicationSet,
        update_set: UpdateMedicationSet,
        delete_set: DeleteMedicationSet,
        family_service: FamilyService | None = None,
    ) -> None:
        self._get_user = get_user
        self._list_regimens = list_regimens
        self._create_set = create_set
        self._list_sets = list_sets
        self._take_set = take_set
        self._get_set = get_set
        self._update_set = update_set
        self._delete_set = delete_set
        self._family_service = family_service

    async def available_regimens(self, telegram_user_id: int) -> list[Regimen]:
        await self._ensure_can_manage(telegram_user_id)
        user = await self._get_user(telegram_user_id)
        assigned = {
            regimen.id for details in await self._list_sets(user.id) for regimen in details.regimens
        }
        return [
            item
            for item in await self._list_regimens(user.id)
            if item.status is RegimenStatus.ACTIVE and item.id not in assigned
        ]

    async def list(self, telegram_user_id: int) -> list[MedicationSetDetails]:
        user = await self._get_user(telegram_user_id)
        return await self._list_sets(user.id)

    async def details(self, telegram_user_id: int, set_id: UUID) -> MedicationSetDetails:
        user = await self._get_user(telegram_user_id)
        return await self._get_set(user.id, set_id)

    async def editable_regimens(
        self, telegram_user_id: int, set_id: UUID
    ) -> builtins.list[Regimen]:
        await self._ensure_can_manage(telegram_user_id)
        user = await self._get_user(telegram_user_id)
        current = await self._get_set(user.id, set_id)
        current_ids = {item.id for item in current.regimens}
        assigned_elsewhere = {
            regimen.id
            for details in await self._list_sets(user.id)
            if details.medication_set.id != set_id
            for regimen in details.regimens
        }
        return [
            item
            for item in await self._list_regimens(user.id)
            if item.id in current_ids
            or (item.status is RegimenStatus.ACTIVE and item.id not in assigned_elsewhere)
        ]

    async def create(
        self,
        telegram_user_id: int,
        *,
        name: str,
        window_start: time,
        window_end: time,
        regimen_ids: tuple[UUID, ...],
    ) -> MedicationSet:
        await self._ensure_can_manage(telegram_user_id)
        user = await self._get_user(telegram_user_id)
        if user.timezone is None:
            raise ValueError("Timezone is required")
        return await self._create_set(
            CreateMedicationSetCommand(
                user.id,
                name,
                window_start,
                window_end,
                user.timezone,
                regimen_ids,
            )
        )

    async def take_all(
        self,
        telegram_user_id: int,
        set_id: UUID,
        local_date: date,
    ) -> int:
        user = await self._get_user(telegram_user_id)
        return await self._take_set(user.id, set_id, local_date)

    async def update(
        self,
        telegram_user_id: int,
        *,
        set_id: UUID,
        name: str,
        window_start: time,
        window_end: time,
        regimen_ids: tuple[UUID, ...],
    ) -> MedicationSetDetails:
        await self._ensure_can_manage(telegram_user_id)
        user = await self._get_user(telegram_user_id)
        return await self._update_set(
            UpdateMedicationSetCommand(
                user.id,
                set_id,
                name,
                window_start,
                window_end,
                regimen_ids,
            )
        )

    async def delete(self, telegram_user_id: int, set_id: UUID) -> None:
        await self._ensure_can_manage(telegram_user_id)
        user = await self._get_user(telegram_user_id)
        await self._delete_set(user.id, set_id)

    async def _ensure_can_manage(self, telegram_user_id: int) -> None:
        if self._family_service is not None:
            await self._family_service.ensure_can_manage_personal_regimens(telegram_user_id)
