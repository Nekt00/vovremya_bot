from typing import Protocol
from uuid import UUID

from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventHistory
from medication_reminder.regimens.domain.regimen import Regimen
from medication_reminder.schedules.domain.schedule import StoredScheduleRule


class ScheduleMaterializationStore(Protocol):
    async def materialize(
        self,
        schedule: StoredScheduleRule,
        events: tuple[IntakeEvent, ...],
        histories: tuple[IntakeEventHistory, ...],
        *,
        regimen: Regimen,
    ) -> None: ...

    async def get_active(self, regimen_id: UUID) -> StoredScheduleRule | None: ...
