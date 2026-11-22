from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.medication_sets.models import MedicationSetModel
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel
from medication_reminder.users.domain.user import User
from medication_reminder.users.infrastructure.models import UserModel


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, telegram_user_id: int) -> User:
        statement = (
            insert(UserModel)
            .values(id=uuid4(), telegram_user_id=telegram_user_id)
            .on_conflict_do_nothing(index_elements=[UserModel.telegram_user_id])
            .returning(UserModel)
        )
        created_user = (await self._session.scalars(statement)).one_or_none()
        if created_user is not None:
            return _to_domain(created_user)

        existing_user = await self.get_by_telegram_user_id(telegram_user_id)
        if existing_user is None:
            raise RuntimeError("User disappeared after a concurrent insert")
        return existing_user

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        statement = select(UserModel).where(UserModel.telegram_user_id == telegram_user_id)
        model = (await self._session.scalars(statement)).one_or_none()
        return _to_domain(model) if model is not None else None

    async def update_timezone(self, telegram_user_id: int, timezone: str) -> User | None:
        now = datetime.now(UTC)
        async with self._session.begin_nested():
            model = (
                await self._session.scalars(
                    select(UserModel)
                    .where(UserModel.telegram_user_id == telegram_user_id)
                    .with_for_update()
                )
            ).one_or_none()
            if model is None:
                return None
            previous_timezone = model.timezone
            if previous_timezone is not None and previous_timezone != timezone:
                await self._move_future_events(
                    model.id,
                    previous_timezone=previous_timezone,
                    timezone=timezone,
                    now=now,
                )
            model.timezone = timezone
            model.updated_at = now
            await self._session.execute(
                update(MedicationSetModel)
                .where(MedicationSetModel.user_id == model.id)
                .values(timezone=timezone, updated_at=now)
            )
            await self._session.execute(
                update(ScheduleRuleModel)
                .where(
                    ScheduleRuleModel.regimen_id.in_(
                        select(RegimenModel.id).where(RegimenModel.user_id == model.id)
                    ),
                    ScheduleRuleModel.active.is_(True),
                )
                .values(timezone=timezone)
            )
            await self._session.flush()
            return _to_domain(model)

    async def _move_future_events(
        self,
        user_id: object,
        *,
        previous_timezone: str,
        timezone: str,
        now: datetime,
    ) -> None:
        events = list(
            (
                await self._session.scalars(
                    select(IntakeEventModel)
                    .join(RegimenModel, RegimenModel.id == IntakeEventModel.regimen_id)
                    .where(
                        RegimenModel.user_id == user_id,
                        IntakeEventModel.status == "scheduled",
                        IntakeEventModel.scheduled_at > now,
                    )
                    .with_for_update()
                )
            ).all()
        )
        old_zone = ZoneInfo(previous_timezone)
        new_zone = ZoneInfo(timezone)
        for event in events:
            local_wall_time = _as_utc(event.scheduled_at).astimezone(old_zone).replace(tzinfo=None)
            event.scheduled_at = local_wall_time.replace(tzinfo=new_zone).astimezone(UTC)
            event.timezone = timezone
            event.updated_at = now

    async def update_reminder_preferences(
        self,
        telegram_user_id: int,
        *,
        repeat_minutes: int | None = None,
        enabled: bool | None = None,
    ) -> User | None:
        values: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if repeat_minutes is not None:
            values["reminder_repeat_minutes"] = repeat_minutes
        if enabled is not None:
            values["reminders_enabled"] = enabled
        statement = (
            update(UserModel)
            .where(UserModel.telegram_user_id == telegram_user_id)
            .values(**values)
            .returning(UserModel)
        )
        model = (await self._session.scalars(statement)).one_or_none()
        return _to_domain(model) if model is not None else None

    async def export_user_data(self, telegram_user_id: int) -> dict[str, object] | None:
        user = (
            await self._session.scalars(
                select(UserModel).where(UserModel.telegram_user_id == telegram_user_id)
            )
        ).one_or_none()
        if user is None:
            return None
        regimens = list(
            (
                await self._session.scalars(
                    select(RegimenModel)
                    .where(RegimenModel.user_id == user.id)
                    .order_by(RegimenModel.created_at)
                )
            ).all()
        )
        regimen_ids = [item.id for item in regimens]
        events = (
            list(
                (
                    await self._session.scalars(
                        select(IntakeEventModel)
                        .where(IntakeEventModel.regimen_id.in_(regimen_ids))
                        .order_by(IntakeEventModel.scheduled_at)
                    )
                ).all()
            )
            if regimen_ids
            else []
        )
        return {
            "user": {
                "telegram_user_id": user.telegram_user_id,
                "timezone": user.timezone,
                "reminder_repeat_minutes": user.reminder_repeat_minutes,
                "reminders_enabled": user.reminders_enabled,
                "created_at": _as_utc(user.created_at).isoformat(),
            },
            "regimens": [
                {
                    "id": str(item.id),
                    "medication_name": item.medication_name,
                    "medication_form": item.medication_form,
                    "dose_amount": str(item.dose_amount),
                    "dose_unit": item.dose_unit,
                    "start_date": item.start_date.isoformat(),
                    "total_intakes": item.total_intakes,
                    "end_date": item.end_date.isoformat() if item.end_date else None,
                    "status": item.status,
                }
                for item in regimens
            ],
            "intake_events": [
                {
                    "id": str(item.id),
                    "regimen_id": str(item.regimen_id),
                    "scheduled_at": _as_utc(item.scheduled_at).isoformat(),
                    "status": item.status,
                    "resolved_at": (
                        _as_utc(item.resolved_at).isoformat() if item.resolved_at else None
                    ),
                }
                for item in events
            ],
        }

    async def delete_user_data(self, telegram_user_id: int) -> bool:
        deleted = await self._session.scalars(
            delete(UserModel)
            .where(UserModel.telegram_user_id == telegram_user_id)
            .returning(UserModel.id)
        )
        return deleted.one_or_none() is not None


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        telegram_user_id=model.telegram_user_id,
        timezone=model.timezone,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
        reminder_repeat_minutes=model.reminder_repeat_minutes,
        reminders_enabled=model.reminders_enabled,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Database returned a timestamp without timezone information")
    return value.astimezone(UTC)
