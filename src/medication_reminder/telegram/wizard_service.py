from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from medication_reminder.families.service import FamilyService
from medication_reminder.medication_sets.application import (
    AddRegimenToMedicationSet,
    CreateMedicationSet,
    CreateMedicationSetCommand,
)
from medication_reminder.regimens.application.use_cases import (
    CreateRegimen,
    CreateRegimenCommand,
)
from medication_reminder.schedules.application.use_cases import MaterializeSchedule
from medication_reminder.telegram.clock import Clock
from medication_reminder.telegram.service import TimezoneRequiredError
from medication_reminder.telegram.wizard_models import (
    NewRegimenCommand,
    required_horizon_days,
)
from medication_reminder.users.application.use_cases import GetOrCreateUser


@dataclass(frozen=True, slots=True)
class SavedRegimen:
    events_count: int


class StaleStartDateError(ValueError):
    pass


class WizardApplicationService:
    def __init__(
        self,
        get_or_create_user: GetOrCreateUser,
        create_regimen: CreateRegimen,
        materialize_schedule: MaterializeSchedule,
        create_medication_set: CreateMedicationSet,
        add_regimen_to_set: AddRegimenToMedicationSet,
        family_service: FamilyService | None = None,
        *,
        clock: Clock,
    ) -> None:
        self._get_or_create_user = get_or_create_user
        self._create_regimen = create_regimen
        self._materialize_schedule = materialize_schedule
        self._create_medication_set = create_medication_set
        self._add_regimen_to_set = add_regimen_to_set
        self._family_service = family_service
        self._clock = clock

    async def require_timezone(self, telegram_user_id: int) -> str:
        user = await self._get_or_create_user(telegram_user_id)
        if user.timezone is None:
            raise TimezoneRequiredError
        return user.timezone

    async def local_today(
        self,
        telegram_user_id: int,
        target_telegram_user_id: int | None = None,
    ) -> date:
        timezone = await self.require_timezone(target_telegram_user_id or telegram_user_id)
        return self._clock().astimezone(ZoneInfo(timezone)).date()

    async def save(
        self,
        telegram_user_id: int,
        command: NewRegimenCommand,
        *,
        target_user_id: UUID | None = None,
        family_group_id: UUID | None = None,
    ) -> SavedRegimen:
        actor = await self._get_or_create_user(telegram_user_id)
        if target_user_id is None:
            if self._family_service is not None:
                await self._family_service.ensure_can_manage_personal_regimens(telegram_user_id)
            user = actor
        else:
            if family_group_id is None:
                raise ValueError("Family group is required for delegated assignment")
            if self._family_service is None:
                raise ValueError("Family assignments are not configured")
            family_target = await self._family_service.resolve_target(
                telegram_user_id,
                target_user_id=target_user_id,
                group_id=family_group_id,
            )
            user = await self._get_or_create_user(family_target.telegram_user_id)
        if user.timezone is None:
            raise TimezoneRequiredError
        local_today = self._clock().astimezone(ZoneInfo(user.timezone)).date()
        if command.start_date < local_today:
            raise StaleStartDateError("Дата начала уже прошла; начните заполнение заново")
        regimen = await self._create_regimen(
            CreateRegimenCommand(
                user_id=user.id,
                medication_name=command.medication_name,
                medication_form=command.medication_form,
                dose_amount=command.dose_amount,
                dose_unit=command.dose_unit,
                start_date=command.start_date,
                total_intakes=command.total_intakes,
                end_date=command.end_date,
                meal_timing=command.meal_timing,
            )
        )
        window_end = materialization_window_end(command, user.timezone)
        result = await self._materialize_schedule(
            regimen,
            command.rule,
            user.timezone,
            window_end=window_end,
        )
        if command.medication_set is not None:
            set_target = command.medication_set
            if set_target.set_id is None:
                await self._create_medication_set(
                    CreateMedicationSetCommand(
                        user.id,
                        set_target.name,
                        set_target.window_start,
                        set_target.window_end,
                        user.timezone,
                        (regimen.id,),
                    )
                )
            else:
                await self._add_regimen_to_set(user.id, set_target.set_id, regimen.id)
        if target_user_id is not None and family_group_id is not None:
            if self._family_service is None:
                raise ValueError("Family assignments are not configured")
            await self._family_service.record_assignment(
                regimen_id=regimen.id,
                owner_telegram_id=telegram_user_id,
                target_user_id=target_user_id,
                group_id=family_group_id,
            )
        return SavedRegimen(events_count=len(result.events))


def materialization_window_end(command: NewRegimenCommand, timezone: str) -> datetime:
    if command.end_date is not None:
        final_date = command.end_date
    else:
        final_date = command.start_date + timedelta(days=required_horizon_days(command) - 1)
    next_midnight = datetime.combine(final_date + timedelta(days=1), time.min, ZoneInfo(timezone))
    return (next_midnight - timedelta(microseconds=1)).astimezone(UTC)
