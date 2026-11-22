from datetime import datetime
from typing import Protocol
from uuid import UUID

from medication_reminder.regimens.domain.regimen import Regimen, RegimenStatus


class RegimenRepository(Protocol):
    async def add(self, regimen: Regimen) -> Regimen: ...

    async def list_for_user(self, user_id: UUID) -> list[Regimen]: ...

    async def get_for_user(self, regimen_id: UUID, user_id: UUID) -> Regimen | None: ...

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
    ) -> Regimen | None: ...


class RegimenDeletionRepository(Protocol):
    async def delete_for_user(self, regimen_id: UUID, user_id: UUID) -> bool: ...
