from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventHistory
from medication_reminder.medication_sets.application import (
    AddRegimenToMedicationSet,
    CreateMedicationSet,
)
from medication_reminder.medication_sets.domain import MedicationSet, MedicationSetDetails
from medication_reminder.regimens.application.use_cases import CreateRegimen
from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.schedules.application.use_cases import MaterializeSchedule
from medication_reminder.schedules.domain.rules import DailyScheduleRule, IntervalScheduleRule
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.telegram.wizard_models import MedicationSetTarget, NewRegimenCommand
from medication_reminder.telegram.wizard_service import WizardApplicationService
from medication_reminder.users.application.use_cases import GetOrCreateUser
from medication_reminder.users.domain.user import User


class FakeUserRepository:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_or_create(self, telegram_user_id: int) -> User:
        return self.user

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        return self.user

    async def update_timezone(self, telegram_user_id: int, timezone: str) -> User | None:
        return self.user


class FakeRegimenRepository:
    def __init__(self) -> None:
        self.items: list[Regimen] = []

    async def add(self, regimen: Regimen) -> Regimen:
        self.items.append(regimen)
        return regimen

    async def list_for_user(self, user_id: UUID) -> list[Regimen]:
        return [item for item in self.items if item.user_id == user_id]

    async def get_for_user(self, regimen_id: UUID, user_id: UUID) -> Regimen | None:
        return next(
            (item for item in self.items if item.id == regimen_id and item.user_id == user_id),
            None,
        )

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
        del cancel_outstanding, cancel_overdue
        return None


class FakeScheduleStore:
    def __init__(self) -> None:
        self.events: tuple[IntakeEvent, ...] = ()

    async def materialize(
        self,
        schedule: StoredScheduleRule,
        events: tuple[IntakeEvent, ...],
        histories: tuple[IntakeEventHistory, ...],
        *,
        regimen: Regimen,
    ) -> None:
        del regimen
        self.events = events

    async def get_active(self, regimen_id: UUID) -> StoredScheduleRule | None:
        return None


class FakeMedicationSetRepository:
    def __init__(self) -> None:
        self.created: tuple[MedicationSet, tuple[UUID, ...]] | None = None
        self.added: tuple[UUID, UUID, UUID] | None = None

    async def create(self, medication_set: MedicationSet, regimen_ids: tuple[UUID, ...]) -> bool:
        self.created = medication_set, regimen_ids
        return True

    async def list_for_user(self, user_id: UUID) -> list[MedicationSetDetails]:
        return []

    async def get_for_user(self, user_id: UUID, set_id: UUID) -> MedicationSetDetails | None:
        return None

    async def update(self, medication_set: MedicationSet, regimen_ids: tuple[UUID, ...]) -> bool:
        return False

    async def delete(self, user_id: UUID, set_id: UUID) -> bool:
        return False

    async def add_member(self, user_id: UUID, set_id: UUID, regimen_id: UUID) -> bool:
        self.added = user_id, set_id, regimen_id
        return True

    async def take_all(
        self,
        user_id: UUID,
        set_id: UUID,
        local_date: date,
        *,
        occurred_at: datetime,
    ) -> int:
        return 0


@pytest.mark.asyncio
async def test_confirmation_creates_regimen_and_all_35_interval_events() -> None:
    service, regimens, schedules = _service()
    command = _command(IntervalScheduleRule(3, (time(10),)), total_intakes=35)

    result = await service.save(42, command)

    assert result.events_count == 35
    assert len(regimens.items) == 1
    assert schedules.events[-1].scheduled_at == datetime(2027, 1, 30, 7, tzinfo=UTC)


@pytest.mark.asyncio
async def test_open_ended_confirmation_materializes_90_days() -> None:
    service, _, schedules = _service()

    result = await service.save(42, _command(DailyScheduleRule((time(10),))))

    assert result.events_count == 90
    assert len(schedules.events) == 90


@pytest.mark.asyncio
async def test_confirmation_adds_new_regimen_to_selected_set() -> None:
    service, regimens, _, medication_sets = _service_with_sets()
    set_id = uuid4()
    target = MedicationSetTarget(set_id, "Утро", time(6), time(12))

    await service.save(42, _command(DailyScheduleRule((time(6),)), target=target))

    assert medication_sets.added == (regimens.items[0].user_id, set_id, regimens.items[0].id)


@pytest.mark.asyncio
async def test_confirmation_creates_selected_new_set_with_regimen() -> None:
    service, regimens, _, medication_sets = _service_with_sets()
    target = MedicationSetTarget(None, "После завтрака", time(8), time(11))

    await service.save(42, _command(DailyScheduleRule((time(8),)), target=target))

    assert medication_sets.created is not None
    created, members = medication_sets.created
    assert created.name == "После завтрака"
    assert members == (regimens.items[0].id,)


def _service() -> tuple[WizardApplicationService, FakeRegimenRepository, FakeScheduleStore]:
    service, regimens, schedules, _ = _service_with_sets()
    return service, regimens, schedules


def _service_with_sets() -> tuple[
    WizardApplicationService,
    FakeRegimenRepository,
    FakeScheduleStore,
    FakeMedicationSetRepository,
]:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    user = User(uuid4(), 42, "Europe/Moscow", now, now)
    regimens = FakeRegimenRepository()
    schedules = FakeScheduleStore()
    medication_sets = FakeMedicationSetRepository()
    service = WizardApplicationService(
        GetOrCreateUser(FakeUserRepository(user)),
        CreateRegimen(regimens, clock=lambda: now),
        MaterializeSchedule(schedules, clock=lambda: now),
        CreateMedicationSet(medication_sets, clock=lambda: now),
        AddRegimenToMedicationSet(medication_sets),
        clock=lambda: now,
    )
    return service, regimens, schedules, medication_sets


def _command(
    rule: DailyScheduleRule | IntervalScheduleRule,
    *,
    total_intakes: int | None = None,
    target: MedicationSetTarget | None = None,
) -> NewRegimenCommand:
    return NewRegimenCommand(
        medication_name="Препарат",
        medication_form=MedicationForm.INJECTION,
        dose_amount=Decimal("1"),
        dose_unit="мг",
        start_date=date(2026, 10, 20),
        rule=rule,
        total_intakes=total_intakes,
        end_date=None,
        medication_set=target,
    )
