from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from medication_reminder.regimens.application.repositories import RegimenRepository
from medication_reminder.regimens.domain.regimen import (
    MealTiming,
    MedicationForm,
    Regimen,
    RegimenStatus,
)


class RegimenNotFoundError(LookupError):
    pass


class RegimenUpdateConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CreateRegimenCommand:
    user_id: UUID
    medication_name: str
    medication_form: MedicationForm
    dose_amount: Decimal
    dose_unit: str
    start_date: date
    total_intakes: int | None = None
    end_date: date | None = None
    meal_timing: MealTiming = MealTiming.INDEPENDENT


class CreateRegimen:
    def __init__(
        self,
        repository: RegimenRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory

    async def __call__(self, command: CreateRegimenCommand) -> Regimen:
        now = self._clock()
        regimen = Regimen(
            id=self._id_factory(),
            user_id=command.user_id,
            medication_name=command.medication_name,
            medication_form=command.medication_form,
            dose_amount=command.dose_amount,
            dose_unit=command.dose_unit,
            start_date=command.start_date,
            total_intakes=command.total_intakes,
            end_date=command.end_date,
            status=RegimenStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            meal_timing=command.meal_timing,
        )
        return await self._repository.add(regimen)


class ListUserRegimens:
    def __init__(self, repository: RegimenRepository) -> None:
        self._repository = repository

    async def __call__(self, user_id: UUID) -> list[Regimen]:
        return await self._repository.list_for_user(user_id)


class GetUserRegimen:
    def __init__(self, repository: RegimenRepository) -> None:
        self._repository = repository

    async def __call__(self, user_id: UUID, regimen_id: UUID) -> Regimen:
        regimen = await self._repository.get_for_user(regimen_id, user_id)
        if regimen is None:
            raise RegimenNotFoundError(f"Regimen {regimen_id} was not found")
        return regimen


class ChangeRegimenStatus:
    def __init__(
        self,
        repository: RegimenRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def __call__(
        self,
        user_id: UUID,
        regimen_id: UUID,
        target_status: RegimenStatus,
    ) -> Regimen:
        current = await self._repository.get_for_user(regimen_id, user_id)
        if current is None:
            raise RegimenNotFoundError(f"Regimen {regimen_id} was not found")
        if current.status is target_status:
            return current

        transitioned = current.transition_to(target_status, at=self._clock())
        updated = await self._repository.update_status(
            regimen_id,
            user_id,
            expected_status=current.status,
            target_status=transitioned.status,
            updated_at=transitioned.updated_at,
            cancel_outstanding=target_status is RegimenStatus.COMPLETED,
            cancel_overdue=(
                current.status is RegimenStatus.PAUSED and target_status is RegimenStatus.ACTIVE
            ),
        )
        if updated is None:
            raise RegimenUpdateConflictError("Regimen was changed concurrently")
        return updated
