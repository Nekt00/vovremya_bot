from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Time, and_, cast, exists, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.domain.event import IntakeEventStatus
from medication_reminder.intake_events.infrastructure.models import (
    IntakeEventHistoryModel,
    IntakeEventModel,
)
from medication_reminder.medication_sets.models import (
    MedicationSetMemberModel,
    MedicationSetModel,
)
from medication_reminder.regimens.domain.regimen import MealTiming, MedicationForm
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.reminders.models import ReminderAttemptModel
from medication_reminder.users.infrastructure.models import UserModel


@dataclass(frozen=True, slots=True)
class ClaimedReminder:
    attempt_id: UUID
    claim_token: UUID
    event_id: UUID
    telegram_user_id: int
    medication_name: str
    medication_form: MedicationForm
    dose_amount: Decimal
    dose_unit: str
    scheduled_at: datetime
    timezone: str
    meal_timing: MealTiming = MealTiming.INDEPENDENT


@dataclass(frozen=True, slots=True)
class SetReminderItem:
    event_id: UUID
    medication_name: str
    medication_form: MedicationForm
    dose_amount: Decimal
    dose_unit: str
    meal_timing: MealTiming = MealTiming.INDEPENDENT


@dataclass(frozen=True, slots=True)
class ClaimedSetReminder:
    attempt_id: UUID
    claim_token: UUID
    set_id: UUID
    set_name: str
    local_date: date
    telegram_user_id: int
    window_end: datetime
    timezone: str
    items: tuple[SetReminderItem, ...]


class SqlAlchemyReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_batch(
        self,
        *,
        now: datetime,
        batch_size: int,
        retry_interval: timedelta,
        claim_timeout: timedelta,
    ) -> list[ClaimedReminder]:
        now = _as_utc(now)
        blocking_attempt = exists(
            select(ReminderAttemptModel.id).where(
                ReminderAttemptModel.event_id == IntakeEventModel.id,
                or_(
                    ReminderAttemptModel.status == "abandoned",
                    and_(
                        ReminderAttemptModel.status == "sent",
                        ReminderAttemptModel.sent_at
                        > now
                        - UserModel.reminder_repeat_minutes * literal_column("INTERVAL '1 minute'"),
                    ),
                    and_(
                        ReminderAttemptModel.status == "claimed",
                        ReminderAttemptModel.claimed_at > now - claim_timeout,
                    ),
                    and_(
                        ReminderAttemptModel.status == "failed",
                        ReminderAttemptModel.updated_at > now - retry_interval,
                    ),
                ),
            )
        )
        active_set_member = exists(
            select(MedicationSetMemberModel.regimen_id)
            .join(
                MedicationSetModel,
                MedicationSetModel.id == MedicationSetMemberModel.set_id,
            )
            .where(
                MedicationSetMemberModel.regimen_id == IntakeEventModel.regimen_id,
                MedicationSetModel.active.is_(True),
            )
        )
        statement = (
            select(IntakeEventModel, UserModel)
            .join(RegimenModel, IntakeEventModel.regimen_id == RegimenModel.id)
            .join(UserModel, RegimenModel.user_id == UserModel.id)
            .where(
                RegimenModel.status == "active",
                UserModel.timezone.is_not(None),
                UserModel.reminders_enabled.is_(True),
                ~active_set_member,
                or_(
                    and_(
                        IntakeEventModel.status == IntakeEventStatus.SCHEDULED.value,
                        IntakeEventModel.scheduled_at <= now,
                    ),
                    and_(
                        IntakeEventModel.status == IntakeEventStatus.SNOOZED.value,
                        IntakeEventModel.snoozed_until <= now,
                    ),
                    and_(
                        IntakeEventModel.status == IntakeEventStatus.DUE.value,
                        ~blocking_attempt,
                    ),
                ),
            )
            .order_by(IntakeEventModel.scheduled_at, IntakeEventModel.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True, of=IntakeEventModel)
        )
        rows = (await self._session.execute(statement)).all()
        claimed: list[ClaimedReminder] = []
        for event, user in rows:
            user_repeat_interval = timedelta(minutes=user.reminder_repeat_minutes)
            if event.status != IntakeEventStatus.DUE.value:
                previous_status = event.status
                event.status = IntakeEventStatus.DUE.value
                event.snoozed_until = None
                event.updated_at = now
                self._session.add(
                    IntakeEventHistoryModel(
                        id=uuid4(),
                        event_id=event.id,
                        from_status=previous_status,
                        to_status=IntakeEventStatus.DUE.value,
                        occurred_at=now,
                        source="system",
                    )
                )
                await self._session.flush()

            activation = _as_utc(event.updated_at)
            elapsed = max(0, int((now - activation).total_seconds()))
            repeat_seconds = int(user_repeat_interval.total_seconds())
            slot = elapsed // repeat_seconds
            scheduled_for = activation + slot * user_repeat_interval
            key = f"{event.id}:{activation.isoformat()}:{slot}"
            attempt = (
                await self._session.scalars(
                    select(ReminderAttemptModel)
                    .where(ReminderAttemptModel.idempotency_key == key)
                    .with_for_update()
                )
            ).one_or_none()
            if attempt is not None and not _can_reclaim(
                attempt,
                now=now,
                retry_interval=retry_interval,
                claim_timeout=claim_timeout,
            ):
                continue

            claim_token = uuid4()
            if attempt is None:
                attempt = ReminderAttemptModel(
                    id=uuid4(),
                    event_id=event.id,
                    idempotency_key=key,
                    scheduled_for=scheduled_for,
                    status="claimed",
                    claim_token=claim_token,
                    claimed_at=now,
                    attempt_count=1,
                    updated_at=now,
                )
                self._session.add(attempt)
            else:
                attempt.status = "claimed"
                attempt.claim_token = claim_token
                attempt.claimed_at = now
                attempt.failure_reason = None
                attempt.attempt_count += 1
                attempt.updated_at = now
            await self._session.flush()
            claimed.append(
                ClaimedReminder(
                    attempt_id=attempt.id,
                    claim_token=claim_token,
                    event_id=event.id,
                    telegram_user_id=user.telegram_user_id,
                    medication_name=event.medication_name,
                    medication_form=MedicationForm(event.medication_form),
                    dose_amount=event.dose_amount,
                    dose_unit=event.dose_unit,
                    scheduled_at=_as_utc(event.scheduled_at),
                    timezone=event.timezone,
                    meal_timing=MealTiming(event.meal_timing),
                )
            )
        return claimed

    async def claim_set_batch(
        self,
        *,
        now: datetime,
        batch_size: int,
        retry_interval: timedelta,
        claim_timeout: timedelta,
    ) -> list[ClaimedSetReminder]:
        now = _as_utc(now)
        local_time = cast(func.timezone(MedicationSetModel.timezone, now), Time)
        sets = (
            await self._session.execute(
                select(MedicationSetModel, UserModel)
                .join(UserModel, UserModel.id == MedicationSetModel.user_id)
                .where(
                    MedicationSetModel.active.is_(True),
                    UserModel.reminders_enabled.is_(True),
                    MedicationSetModel.window_start <= local_time,
                    MedicationSetModel.window_end > local_time,
                )
                .order_by(MedicationSetModel.window_start, MedicationSetModel.id)
            )
        ).all()
        claimed: list[ClaimedSetReminder] = []
        for medication_set, user in sets:
            if len(claimed) >= batch_size:
                break
            zone = ZoneInfo(medication_set.timezone)
            local_now = now.astimezone(zone)
            local_date = local_now.date()
            window_start = datetime.combine(
                local_date, medication_set.window_start, zone
            ).astimezone(UTC)
            window_end = datetime.combine(local_date, medication_set.window_end, zone).astimezone(
                UTC
            )
            if not window_start <= now < window_end:
                continue
            events = list(
                (
                    await self._session.scalars(
                        select(IntakeEventModel)
                        .join(
                            MedicationSetMemberModel,
                            MedicationSetMemberModel.regimen_id == IntakeEventModel.regimen_id,
                        )
                        .join(RegimenModel, RegimenModel.id == IntakeEventModel.regimen_id)
                        .where(
                            MedicationSetMemberModel.set_id == medication_set.id,
                            RegimenModel.status == "active",
                            IntakeEventModel.scheduled_at >= window_start,
                            IntakeEventModel.scheduled_at < window_end,
                            IntakeEventModel.scheduled_at <= now,
                            or_(
                                IntakeEventModel.status.in_(("scheduled", "due")),
                                and_(
                                    IntakeEventModel.status == "snoozed",
                                    IntakeEventModel.snoozed_until <= now,
                                ),
                            ),
                        )
                        .order_by(IntakeEventModel.scheduled_at, IntakeEventModel.id)
                        .with_for_update(skip_locked=True, of=IntakeEventModel)
                    )
                ).all()
            )
            if not events:
                continue
            for event in events:
                if event.status != "due":
                    previous = event.status
                    event.status = "due"
                    event.snoozed_until = None
                    event.updated_at = now
                    self._session.add(
                        IntakeEventHistoryModel(
                            id=uuid4(),
                            event_id=event.id,
                            from_status=previous,
                            to_status="due",
                            occurred_at=now,
                            source="system",
                        )
                    )
            await self._session.flush()
            user_repeat_interval = timedelta(minutes=user.reminder_repeat_minutes)
            slot = int((now - window_start).total_seconds()) // int(
                user_repeat_interval.total_seconds()
            )
            key = f"set:{medication_set.id}:{local_date.isoformat()}:{slot}"
            attempt = (
                await self._session.scalars(
                    select(ReminderAttemptModel)
                    .where(ReminderAttemptModel.idempotency_key == key)
                    .with_for_update()
                )
            ).one_or_none()
            if attempt is not None and not _can_reclaim(
                attempt,
                now=now,
                retry_interval=retry_interval,
                claim_timeout=claim_timeout,
            ):
                continue
            claim_token = uuid4()
            if attempt is None:
                attempt = ReminderAttemptModel(
                    id=uuid4(),
                    event_id=events[0].id,
                    idempotency_key=key,
                    scheduled_for=window_start + slot * user_repeat_interval,
                    status="claimed",
                    claim_token=claim_token,
                    claimed_at=now,
                    attempt_count=1,
                    updated_at=now,
                )
                self._session.add(attempt)
            else:
                attempt.status = "claimed"
                attempt.claim_token = claim_token
                attempt.claimed_at = now
                attempt.failure_reason = None
                attempt.attempt_count += 1
                attempt.updated_at = now
            await self._session.flush()
            claimed.append(
                ClaimedSetReminder(
                    attempt.id,
                    claim_token,
                    medication_set.id,
                    medication_set.name,
                    local_date,
                    user.telegram_user_id,
                    window_end,
                    medication_set.timezone,
                    tuple(
                        SetReminderItem(
                            event.id,
                            event.medication_name,
                            MedicationForm(event.medication_form),
                            event.dose_amount,
                            event.dose_unit,
                            MealTiming(event.meal_timing),
                        )
                        for event in events
                    ),
                )
            )
        return claimed

    async def is_set_deliverable(
        self,
        attempt_id: UUID,
        claim_token: UUID,
        set_id: UUID,
        event_ids: tuple[UUID, ...],
    ) -> bool:
        attempt_exists = exists(
            select(ReminderAttemptModel.id).where(
                ReminderAttemptModel.id == attempt_id,
                ReminderAttemptModel.claim_token == claim_token,
                ReminderAttemptModel.status == "claimed",
            )
        )
        statement = (
            select(IntakeEventModel.id)
            .join(RegimenModel, RegimenModel.id == IntakeEventModel.regimen_id)
            .join(
                MedicationSetMemberModel,
                MedicationSetMemberModel.regimen_id == IntakeEventModel.regimen_id,
            )
            .join(
                MedicationSetModel,
                MedicationSetModel.id == MedicationSetMemberModel.set_id,
            )
            .where(
                attempt_exists,
                MedicationSetModel.id == set_id,
                MedicationSetModel.active.is_(True),
                RegimenModel.status == "active",
                IntakeEventModel.id.in_(event_ids),
                IntakeEventModel.status == "due",
            )
        )
        return (await self._session.scalars(statement)).first() is not None

    async def mark_sent(
        self,
        attempt_id: UUID,
        claim_token: UUID,
        *,
        sent_at: datetime,
        telegram_message_id: int,
    ) -> bool:
        result = await self._session.scalars(
            update(ReminderAttemptModel)
            .where(
                ReminderAttemptModel.id == attempt_id,
                ReminderAttemptModel.claim_token == claim_token,
                ReminderAttemptModel.status == "claimed",
            )
            .values(
                status="sent",
                sent_at=_as_utc(sent_at),
                telegram_message_id=telegram_message_id,
                failure_reason=None,
                updated_at=_as_utc(sent_at),
            )
            .returning(ReminderAttemptModel.id)
        )
        return result.one_or_none() is not None

    async def is_deliverable(self, attempt_id: UUID, claim_token: UUID) -> bool:
        statement = (
            select(ReminderAttemptModel.id)
            .join(IntakeEventModel, ReminderAttemptModel.event_id == IntakeEventModel.id)
            .join(RegimenModel, IntakeEventModel.regimen_id == RegimenModel.id)
            .where(
                ReminderAttemptModel.id == attempt_id,
                ReminderAttemptModel.claim_token == claim_token,
                ReminderAttemptModel.status == "claimed",
                IntakeEventModel.status == IntakeEventStatus.DUE.value,
                RegimenModel.status == "active",
            )
        )
        return (await self._session.scalars(statement)).one_or_none() is not None

    async def mark_failed(
        self,
        attempt_id: UUID,
        claim_token: UUID,
        *,
        failed_at: datetime,
        reason: str,
    ) -> bool:
        result = await self._session.scalars(
            update(ReminderAttemptModel)
            .where(
                ReminderAttemptModel.id == attempt_id,
                ReminderAttemptModel.claim_token == claim_token,
                ReminderAttemptModel.status == "claimed",
            )
            .values(
                status="failed",
                failure_reason=reason[:1000],
                updated_at=_as_utc(failed_at),
            )
            .returning(ReminderAttemptModel.id)
        )
        return result.one_or_none() is not None

    async def mark_abandoned(
        self,
        attempt_id: UUID,
        claim_token: UUID,
        *,
        failed_at: datetime,
        reason: str,
    ) -> bool:
        failed_at = _as_utc(failed_at)
        result = await self._session.scalars(
            update(ReminderAttemptModel)
            .where(
                ReminderAttemptModel.id == attempt_id,
                ReminderAttemptModel.claim_token == claim_token,
                ReminderAttemptModel.status == "claimed",
            )
            .values(
                status="abandoned",
                failure_reason=reason[:1000],
                updated_at=failed_at,
            )
            .returning(ReminderAttemptModel.id)
        )
        return result.one_or_none() is not None


def _can_reclaim(
    attempt: ReminderAttemptModel,
    *,
    now: datetime,
    retry_interval: timedelta,
    claim_timeout: timedelta,
) -> bool:
    if attempt.status in {"sent", "abandoned"}:
        return False
    if attempt.status == "failed":
        return _as_utc(attempt.updated_at) <= now - retry_interval
    return _as_utc(attempt.claimed_at) <= now - claim_timeout


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)
