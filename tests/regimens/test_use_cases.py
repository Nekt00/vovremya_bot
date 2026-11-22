from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from medication_reminder.regimens.application.repositories import RegimenRepository
from medication_reminder.regimens.application.use_cases import (
    ChangeRegimenStatus,
    CreateRegimen,
    CreateRegimenCommand,
    GetUserRegimen,
    ListUserRegimens,
    RegimenNotFoundError,
    RegimenUpdateConflictError,
)
from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)


class InMemoryRegimenRepository:
    def __init__(self) -> None:
        self.regimens: dict[UUID, Regimen] = {}
        self.force_update_conflict = False
        self.cancel_outstanding = False
        self.cancel_overdue = False

    async def add(self, regimen: Regimen) -> Regimen:
        self.regimens[regimen.id] = regimen
        return regimen

    async def list_for_user(self, user_id: UUID) -> list[Regimen]:
        return [regimen for regimen in self.regimens.values() if regimen.user_id == user_id]

    async def get_for_user(self, regimen_id: UUID, user_id: UUID) -> Regimen | None:
        regimen = self.regimens.get(regimen_id)
        return regimen if regimen is not None and regimen.user_id == user_id else None

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
        self.cancel_outstanding = cancel_outstanding
        self.cancel_overdue = cancel_overdue
        regimen = await self.get_for_user(regimen_id, user_id)
        if self.force_update_conflict or regimen is None or regimen.status is not expected_status:
            return None
        updated = replace(regimen, status=target_status, updated_at=updated_at)
        self.regimens[regimen_id] = updated
        return updated


def assert_regimen_repository(repository: RegimenRepository) -> None:
    assert repository is not None


def make_command(user_id: UUID) -> CreateRegimenCommand:
    return CreateRegimenCommand(
        user_id=user_id,
        medication_name="  Injection X ",
        medication_form=MedicationForm.INJECTION,
        dose_amount=Decimal("1.25"),
        dose_unit=" mg ",
        start_date=date(2026, 10, 18),
        total_intakes=35,
    )


@pytest.mark.asyncio
async def test_create_regimen_starts_active_and_persists_normalized_values() -> None:
    repository = InMemoryRegimenRepository()
    assert_regimen_repository(repository)
    user_id = uuid4()
    regimen_id = uuid4()
    now = datetime(2026, 10, 17, 9, tzinfo=UTC)

    regimen = await CreateRegimen(
        repository,
        clock=lambda: now,
        id_factory=lambda: regimen_id,
    )(make_command(user_id))

    assert regimen.id == regimen_id
    assert regimen.user_id == user_id
    assert regimen.medication_name == "Injection X"
    assert regimen.dose_unit == "mg"
    assert regimen.status is RegimenStatus.ACTIVE
    assert repository.regimens[regimen_id] == regimen


@pytest.mark.asyncio
async def test_list_regimens_returns_only_requested_users_items() -> None:
    repository = InMemoryRegimenRepository()
    first_user = uuid4()
    second_user = uuid4()
    await CreateRegimen(repository)(make_command(first_user))
    await CreateRegimen(repository)(make_command(second_user))

    result = await ListUserRegimens(repository)(first_user)

    assert len(result) == 1
    assert result[0].user_id == first_user


@pytest.mark.asyncio
async def test_change_status_is_scoped_to_owner() -> None:
    repository = InMemoryRegimenRepository()
    owner_id = uuid4()
    regimen = await CreateRegimen(repository)(make_command(owner_id))

    with pytest.raises(RegimenNotFoundError):
        await ChangeRegimenStatus(repository)(
            uuid4(),
            regimen.id,
            RegimenStatus.PAUSED,
        )


@pytest.mark.asyncio
async def test_change_status_detects_concurrent_update() -> None:
    repository = InMemoryRegimenRepository()
    user_id = uuid4()
    regimen = await CreateRegimen(repository)(make_command(user_id))
    repository.force_update_conflict = True

    with pytest.raises(RegimenUpdateConflictError):
        await ChangeRegimenStatus(repository)(
            user_id,
            regimen.id,
            RegimenStatus.PAUSED,
        )


@pytest.mark.asyncio
async def test_change_status_completes_regimen() -> None:
    repository = InMemoryRegimenRepository()
    user_id = uuid4()
    initial_time = datetime(2026, 10, 17, 9, tzinfo=UTC)
    completed_time = datetime(2026, 10, 17, 10, tzinfo=UTC)
    regimen = await CreateRegimen(repository, clock=lambda: initial_time)(make_command(user_id))

    completed = await ChangeRegimenStatus(repository, clock=lambda: completed_time)(
        user_id,
        regimen.id,
        RegimenStatus.COMPLETED,
    )

    assert completed.status is RegimenStatus.COMPLETED
    assert completed.updated_at == completed_time
    assert repository.cancel_outstanding


@pytest.mark.asyncio
async def test_get_regimen_is_scoped_to_owner() -> None:
    repository = InMemoryRegimenRepository()
    owner_id = uuid4()
    regimen = await CreateRegimen(repository)(make_command(owner_id))

    assert await GetUserRegimen(repository)(owner_id, regimen.id) == regimen
    with pytest.raises(RegimenNotFoundError):
        await GetUserRegimen(repository)(uuid4(), regimen.id)


@pytest.mark.asyncio
async def test_repeating_same_status_is_idempotent() -> None:
    repository = InMemoryRegimenRepository()
    user_id = uuid4()
    regimen = await CreateRegimen(repository)(make_command(user_id))

    result = await ChangeRegimenStatus(repository)(user_id, regimen.id, RegimenStatus.ACTIVE)

    assert result == regimen


@pytest.mark.asyncio
async def test_resuming_requests_overdue_event_cancellation() -> None:
    repository = InMemoryRegimenRepository()
    user_id = uuid4()
    regimen = await CreateRegimen(repository)(make_command(user_id))
    paused = await ChangeRegimenStatus(repository)(user_id, regimen.id, RegimenStatus.PAUSED)

    resumed = await ChangeRegimenStatus(repository)(user_id, paused.id, RegimenStatus.ACTIVE)

    assert resumed.status is RegimenStatus.ACTIVE
    assert repository.cancel_overdue
