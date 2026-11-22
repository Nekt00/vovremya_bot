from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Protocol
from uuid import UUID, uuid4

from medication_reminder.medication_sets.domain import MedicationSet, MedicationSetDetails


class MedicationSetError(RuntimeError):
    pass


class MedicationSetConflictError(MedicationSetError):
    pass


@dataclass(frozen=True, slots=True)
class CreateMedicationSetCommand:
    user_id: UUID
    name: str
    window_start: time
    window_end: time
    timezone: str
    regimen_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class UpdateMedicationSetCommand:
    user_id: UUID
    set_id: UUID
    name: str
    window_start: time
    window_end: time
    regimen_ids: tuple[UUID, ...]


class MedicationSetRepository(Protocol):
    async def create(
        self, medication_set: MedicationSet, regimen_ids: tuple[UUID, ...]
    ) -> bool: ...

    async def list_for_user(self, user_id: UUID) -> list[MedicationSetDetails]: ...

    async def get_for_user(self, user_id: UUID, set_id: UUID) -> MedicationSetDetails | None: ...

    async def update(
        self, medication_set: MedicationSet, regimen_ids: tuple[UUID, ...]
    ) -> bool: ...

    async def delete(self, user_id: UUID, set_id: UUID) -> bool: ...

    async def add_member(self, user_id: UUID, set_id: UUID, regimen_id: UUID) -> bool: ...

    async def take_all(
        self,
        user_id: UUID,
        set_id: UUID,
        local_date: date,
        *,
        occurred_at: datetime,
    ) -> int: ...


class CreateMedicationSet:
    def __init__(
        self,
        repository: MedicationSetRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def __call__(self, command: CreateMedicationSetCommand) -> MedicationSet:
        if not command.regimen_ids or len(set(command.regimen_ids)) != len(command.regimen_ids):
            raise MedicationSetError("Choose at least one unique regimen")
        now = self._clock()
        medication_set = MedicationSet(
            id=uuid4(),
            user_id=command.user_id,
            name=command.name,
            window_start=command.window_start,
            window_end=command.window_end,
            timezone=command.timezone,
            active=True,
            created_at=now,
            updated_at=now,
        )
        if not await self._repository.create(medication_set, command.regimen_ids):
            raise MedicationSetConflictError("Regimens are unavailable or already assigned")
        return medication_set


class ListMedicationSets:
    def __init__(self, repository: MedicationSetRepository) -> None:
        self._repository = repository

    async def __call__(self, user_id: UUID) -> list[MedicationSetDetails]:
        return await self._repository.list_for_user(user_id)


class GetMedicationSet:
    def __init__(self, repository: MedicationSetRepository) -> None:
        self._repository = repository

    async def __call__(self, user_id: UUID, set_id: UUID) -> MedicationSetDetails:
        details = await self._repository.get_for_user(user_id, set_id)
        if details is None:
            raise MedicationSetConflictError("Set not found")
        return details


class UpdateMedicationSet:
    def __init__(
        self,
        repository: MedicationSetRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def __call__(self, command: UpdateMedicationSetCommand) -> MedicationSetDetails:
        if not command.regimen_ids or len(set(command.regimen_ids)) != len(command.regimen_ids):
            raise MedicationSetError("Choose at least one unique regimen")
        current = await self._repository.get_for_user(command.user_id, command.set_id)
        if current is None:
            raise MedicationSetConflictError("Set not found")
        value = current.medication_set
        updated = MedicationSet(
            id=value.id,
            user_id=value.user_id,
            name=command.name,
            window_start=command.window_start,
            window_end=command.window_end,
            timezone=value.timezone,
            active=value.active,
            created_at=value.created_at,
            updated_at=self._clock(),
        )
        if not await self._repository.update(updated, command.regimen_ids):
            raise MedicationSetConflictError("Set update conflicts with another set")
        details = await self._repository.get_for_user(command.user_id, command.set_id)
        if details is None:
            raise MedicationSetConflictError("Set not found after update")
        return details


class DeleteMedicationSet:
    def __init__(self, repository: MedicationSetRepository) -> None:
        self._repository = repository

    async def __call__(self, user_id: UUID, set_id: UUID) -> None:
        if not await self._repository.delete(user_id, set_id):
            raise MedicationSetConflictError("Set not found")


class AddRegimenToMedicationSet:
    def __init__(self, repository: MedicationSetRepository) -> None:
        self._repository = repository

    async def __call__(self, user_id: UUID, set_id: UUID, regimen_id: UUID) -> None:
        if not await self._repository.add_member(user_id, set_id, regimen_id):
            raise MedicationSetConflictError("Regimen cannot be added to this set")


class TakeMedicationSet:
    def __init__(
        self,
        repository: MedicationSetRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def __call__(self, user_id: UUID, set_id: UUID, local_date: date) -> int:
        count = await self._repository.take_all(
            user_id,
            set_id,
            local_date,
            occurred_at=self._clock(),
        )
        if count == 0:
            raise MedicationSetConflictError("Set has no pending events")
        return count
