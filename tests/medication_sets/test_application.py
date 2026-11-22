from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

import pytest

from medication_reminder.medication_sets.application import (
    CreateMedicationSet,
    CreateMedicationSetCommand,
    DeleteMedicationSet,
    MedicationSetConflictError,
    MedicationSetError,
    TakeMedicationSet,
    UpdateMedicationSet,
    UpdateMedicationSetCommand,
)
from medication_reminder.medication_sets.domain import MedicationSet, MedicationSetDetails


class FakeRepository:
    def __init__(
        self,
        *,
        accepts: bool = True,
        taken_count: int = 0,
        details: MedicationSetDetails | None = None,
        delete_accepts: bool = True,
    ) -> None:
        self.accepts = accepts
        self.taken_count = taken_count
        self.details = details
        self.delete_accepts = delete_accepts
        self.created: tuple[MedicationSet, tuple[UUID, ...]] | None = None
        self.updated: tuple[MedicationSet, tuple[UUID, ...]] | None = None
        self.added_member: tuple[UUID, UUID, UUID] | None = None
        self.take_request: tuple[UUID, UUID, date, datetime] | None = None

    async def create(
        self,
        medication_set: MedicationSet,
        regimen_ids: tuple[UUID, ...],
    ) -> bool:
        self.created = (medication_set, regimen_ids)
        return self.accepts

    async def list_for_user(self, user_id: UUID) -> list[MedicationSetDetails]:
        return []

    async def get_for_user(self, user_id: UUID, set_id: UUID) -> MedicationSetDetails | None:
        if self.details is None:
            return None
        value = self.details.medication_set
        return self.details if value.user_id == user_id and value.id == set_id else None

    async def update(
        self,
        medication_set: MedicationSet,
        regimen_ids: tuple[UUID, ...],
    ) -> bool:
        if not self.accepts:
            return False
        self.updated = medication_set, regimen_ids
        self.details = MedicationSetDetails(
            medication_set, self.details.regimens if self.details is not None else ()
        )
        return True

    async def delete(self, user_id: UUID, set_id: UUID) -> bool:
        return self.delete_accepts

    async def add_member(self, user_id: UUID, set_id: UUID, regimen_id: UUID) -> bool:
        self.added_member = user_id, set_id, regimen_id
        return self.accepts

    async def take_all(
        self,
        user_id: UUID,
        set_id: UUID,
        local_date: date,
        *,
        occurred_at: datetime,
    ) -> int:
        self.take_request = (user_id, set_id, local_date, occurred_at)
        return self.taken_count


@pytest.mark.asyncio
async def test_create_set_builds_valid_daily_window() -> None:
    repository = FakeRepository()
    regimen_ids = (uuid4(), uuid4())

    result = await CreateMedicationSet(repository)(
        CreateMedicationSetCommand(
            user_id=uuid4(),
            name="  Утро  ",
            window_start=time(6),
            window_end=time(12),
            timezone="Europe/Moscow",
            regimen_ids=regimen_ids,
        )
    )

    assert result.name == "Утро"
    assert result.window_start == time(6)
    assert repository.created == (result, regimen_ids)


@pytest.mark.asyncio
async def test_create_set_requires_unique_members() -> None:
    regimen_id = uuid4()

    with pytest.raises(MedicationSetError):
        await CreateMedicationSet(FakeRepository())(
            CreateMedicationSetCommand(
                uuid4(),
                "Утро",
                time(6),
                time(12),
                "UTC",
                (regimen_id, regimen_id),
            )
        )


@pytest.mark.asyncio
async def test_create_set_reports_repository_conflict() -> None:
    with pytest.raises(MedicationSetConflictError):
        await CreateMedicationSet(FakeRepository(accepts=False))(
            CreateMedicationSetCommand(
                uuid4(),
                "Вечер",
                time(18),
                time(23),
                "UTC",
                (uuid4(),),
            )
        )


def test_set_rejects_reversed_window() -> None:
    now = datetime(2026, 10, 17, tzinfo=UTC)

    with pytest.raises(ValueError):
        MedicationSet(
            uuid4(),
            uuid4(),
            "Утро",
            time(12),
            time(6),
            "UTC",
            True,
            now,
            now,
        )


@pytest.mark.asyncio
async def test_take_set_marks_all_pending_events_at_current_time() -> None:
    now = datetime(2026, 10, 17, 6, tzinfo=UTC)
    repository = FakeRepository(taken_count=2)
    user_id = uuid4()
    set_id = uuid4()
    local_date = date(2026, 10, 17)

    count = await TakeMedicationSet(repository, clock=lambda: now)(user_id, set_id, local_date)

    assert count == 2
    assert repository.take_request == (user_id, set_id, local_date, now)


@pytest.mark.asyncio
async def test_take_set_rejects_empty_or_already_completed_set() -> None:
    with pytest.raises(MedicationSetConflictError):
        await TakeMedicationSet(FakeRepository())(uuid4(), uuid4(), date(2026, 10, 17))


@pytest.mark.asyncio
async def test_update_set_preserves_identity_and_timezone() -> None:
    created_at = datetime(2026, 10, 1, tzinfo=UTC)
    updated_at = datetime(2026, 10, 17, tzinfo=UTC)
    current = MedicationSet(
        uuid4(),
        uuid4(),
        "Утро",
        time(6),
        time(12),
        "Europe/Moscow",
        True,
        created_at,
        created_at,
    )
    repository = FakeRepository(details=MedicationSetDetails(current, ()))
    regimen_ids = (uuid4(), uuid4())

    result = await UpdateMedicationSet(repository, clock=lambda: updated_at)(
        UpdateMedicationSetCommand(
            current.user_id,
            current.id,
            "Раннее утро",
            time(5, 30),
            time(10),
            regimen_ids,
        )
    )

    assert result.medication_set.name == "Раннее утро"
    assert result.medication_set.timezone == "Europe/Moscow"
    assert result.medication_set.created_at == created_at
    assert result.medication_set.updated_at == updated_at
    assert repository.updated == (result.medication_set, regimen_ids)


@pytest.mark.asyncio
async def test_update_set_rejects_missing_set() -> None:
    with pytest.raises(MedicationSetConflictError):
        await UpdateMedicationSet(FakeRepository())(
            UpdateMedicationSetCommand(uuid4(), uuid4(), "Утро", time(6), time(12), (uuid4(),))
        )


@pytest.mark.asyncio
async def test_delete_set_reports_missing_set() -> None:
    with pytest.raises(MedicationSetConflictError):
        await DeleteMedicationSet(FakeRepository(delete_accepts=False))(uuid4(), uuid4())
