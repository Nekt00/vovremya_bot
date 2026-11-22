from datetime import datetime
from typing import Protocol
from uuid import UUID

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.domain.event import (
    IntakeEvent,
    IntakeEventHistory,
    IntakeEventStatus,
)


class IntakeEventRepository(Protocol):
    async def get_for_user(self, event_id: UUID, user_id: UUID) -> IntakeEvent | None: ...

    async def transition(
        self,
        event: IntakeEvent,
        *,
        user_id: UUID,
        expected_status: IntakeEventStatus,
        history: IntakeEventHistory,
    ) -> IntakeEvent | None: ...

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEvent]: ...


class IntakeEventDetailsRepository(Protocol):
    async def list_details_for_user(
        self,
        user_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[IntakeEventDetails]: ...
