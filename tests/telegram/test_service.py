from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.application.use_cases import (
    IntakeEventNotFoundError,
    ListUserIntakeEventDetails,
    TransitionIntakeEvent,
)
from medication_reminder.intake_events.domain.event import (
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
    InvalidIntakeTransitionError,
)
from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.telegram.callbacks import EventAction, EventCallback
from medication_reminder.telegram.service import TelegramApplicationService
from medication_reminder.users.domain.user import User


class FakeUserRepository:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_or_create(self, telegram_user_id: int) -> User:
        return self.user

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        return self.user

    async def update_timezone(self, telegram_user_id: int, timezone: str) -> User | None:
        self.user = replace(self.user, timezone=timezone)
        return self.user


class FakeDetailsRepository:
    def __init__(self) -> None:
        self.window: tuple[datetime, datetime] | None = None

    async def list_details_for_user(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEventDetails]:
        self.window = (window_start, window_end)
        return []


class FakeEventRepository:
    def __init__(self, event: IntakeEvent, owner_id: UUID) -> None:
        self.event = event
        self.owner_id = owner_id

    async def get_for_user(self, event_id: UUID, user_id: UUID) -> IntakeEvent | None:
        return self.event if event_id == self.event.id and user_id == self.owner_id else None

    async def transition(
        self,
        event: IntakeEvent,
        *,
        user_id: UUID,
        expected_status: IntakeEventStatus,
        history: IntakeEventHistory,
    ) -> IntakeEvent | None:
        if user_id != self.owner_id or self.event.status is not expected_status:
            return None
        self.event = event
        return event

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEvent]:
        return []


def make_user() -> User:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    return User(uuid4(), 42, "Europe/Moscow", now, now)


def make_event() -> IntakeEvent:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    return IntakeEvent(
        id=uuid4(),
        regimen_id=uuid4(),
        schedule_rule_id=uuid4(),
        sequence_number=1,
        scheduled_at=now,
        timezone="Europe/Moscow",
        status=IntakeEventStatus.DUE,
        snoozed_until=None,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_intake_screen_is_scoped_to_owned_selected_event() -> None:
    user = make_user()
    event = make_event()
    repository = FakeEventRepository(event, user.id)
    service = TelegramApplicationService(
        FakeUserRepository(user),
        ListUserIntakeEventDetails(FakeDetailsRepository()),
        TransitionIntakeEvent(repository),
        clock=lambda: event.scheduled_at,
    )
    details = [
        IntakeEventDetails(
            event=event if index == 0 else replace(event, id=uuid4()),
            medication_name=name,
            medication_form=MedicationForm.TABLET,
            dose_amount=Decimal("1"),
            dose_unit="таблетка",
        )
        for index, name in enumerate(("Витамин D", "Магний", "Железо"))
    ]
    with patch.object(service, "today", AsyncMock(return_value=(user, details))) as today:
        text, markup = await service.intake_screen(42, event.id)
        today.assert_awaited_once_with(42, current_window=False)
        assert "Витамин D" in text
        assert "Магний" not in text and "Железо" not in text
        actions = [
            EventCallback.decode(row[0].callback_data or "") for row in markup.inline_keyboard[:-1]
        ]
        assert {action.event_id for action in actions} == {event.id}
        assert {action.action for action in actions} == {
            EventAction.TAKE,
            EventAction.SKIP,
            EventAction.SNOOZE,
        }
        with pytest.raises(IntakeEventNotFoundError):
            await service.intake_screen(42, uuid4())
    assert repository.event.status is IntakeEventStatus.DUE


@pytest.mark.asyncio
async def test_today_uses_users_local_calendar_day() -> None:
    user = make_user()
    details_repository = FakeDetailsRepository()
    event_repository = FakeEventRepository(make_event(), user.id)
    now = datetime(2026, 10, 17, 12, tzinfo=UTC)
    service = TelegramApplicationService(
        FakeUserRepository(user),
        ListUserIntakeEventDetails(details_repository),
        TransitionIntakeEvent(event_repository, clock=lambda: now),
        clock=lambda: now,
    )

    await service.today(user.telegram_user_id)

    assert details_repository.window == (
        datetime(2026, 10, 16, 21, tzinfo=UTC),
        datetime(2026, 10, 17, 21, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_history_uses_last_seven_local_calendar_days() -> None:
    user = make_user()
    details_repository = FakeDetailsRepository()
    event_repository = FakeEventRepository(make_event(), user.id)
    now = datetime(2026, 10, 17, 12, tzinfo=UTC)
    service = TelegramApplicationService(
        FakeUserRepository(user),
        ListUserIntakeEventDetails(details_repository),
        TransitionIntakeEvent(event_repository, clock=lambda: now),
        clock=lambda: now,
    )

    await service.history(user.telegram_user_id, days=7)

    assert details_repository.window == (
        datetime(2026, 10, 10, 21, tzinfo=UTC),
        datetime(2026, 10, 17, 21, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_history_rejects_unsupported_period() -> None:
    user = make_user()
    event_repository = FakeEventRepository(make_event(), user.id)
    service = TelegramApplicationService(
        FakeUserRepository(user),
        ListUserIntakeEventDetails(FakeDetailsRepository()),
        TransitionIntakeEvent(event_repository),
        clock=lambda: datetime(2026, 10, 17, 12, tzinfo=UTC),
    )

    with pytest.raises(ValueError):
        await service.history(user.telegram_user_id, days=365)


@pytest.mark.asyncio
async def test_snooze_uses_injected_clock_and_adds_fifteen_minutes() -> None:
    user = make_user()
    event = make_event()
    event_repository = FakeEventRepository(event, user.id)
    now = datetime(2026, 10, 17, 10, tzinfo=UTC)
    service = TelegramApplicationService(
        FakeUserRepository(user),
        ListUserIntakeEventDetails(FakeDetailsRepository()),
        TransitionIntakeEvent(event_repository, clock=lambda: now),
        clock=lambda: now,
    )

    await service.apply_action(
        user.telegram_user_id,
        EventCallback(event.id, EventAction.SNOOZE),
    )

    assert event_repository.event.status is IntakeEventStatus.SNOOZED
    assert event_repository.event.snoozed_until == datetime(2026, 10, 17, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_snooze_cannot_cross_local_day_deadline() -> None:
    user = make_user()
    event = replace(
        make_event(),
        scheduled_at=datetime(2026, 10, 17, 20, 30, tzinfo=UTC),
        updated_at=datetime(2026, 10, 17, 20, 30, tzinfo=UTC),
    )
    event_repository = FakeEventRepository(event, user.id)
    now = datetime(2026, 10, 17, 20, 50, tzinfo=UTC)
    service = TelegramApplicationService(
        FakeUserRepository(user),
        ListUserIntakeEventDetails(FakeDetailsRepository()),
        TransitionIntakeEvent(event_repository, clock=lambda: now),
        clock=lambda: now,
    )

    with pytest.raises(InvalidIntakeTransitionError, match="пределы окна"):
        await service.snooze(user.telegram_user_id, event.id, 15)
