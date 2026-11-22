from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.domain.event import IntakeEventStatus
from medication_reminder.medication_sets.domain import MedicationSetDetails


@dataclass(frozen=True, slots=True)
class UpcomingIntake:
    at: datetime
    label: str


def next_today_intake(
    details: list[IntakeEventDetails], medication_sets: list[MedicationSetDetails], *, now: datetime
) -> UpcomingIntake | None:
    active_sets = {
        regimen.id: item.medication_set
        for item in medication_sets
        if item.medication_set.active
        for regimen in item.regimens
    }
    upcoming = []
    for item in details:
        event = item.event
        if event.status not in {
            IntakeEventStatus.SCHEDULED,
            IntakeEventStatus.DUE,
            IntakeEventStatus.SNOOZED,
        }:
            continue
        at = event.snoozed_until or event.scheduled_at
        if at <= now:
            continue
        zone = ZoneInfo(event.timezone)
        if at.astimezone(zone).date() != now.astimezone(zone).date():
            continue
        medication_set = active_sets.get(event.regimen_id)
        if medication_set is not None:
            set_zone = ZoneInfo(medication_set.timezone)
            scheduled = event.scheduled_at.astimezone(set_zone)
            if not medication_set.window_start <= scheduled.time() < medication_set.window_end:
                continue
            if (
                not medication_set.window_start
                <= at.astimezone(set_zone).time()
                < medication_set.window_end
            ):
                continue
        upcoming.append(
            UpcomingIntake(
                at=at,
                label=medication_set.name if medication_set is not None else item.medication_name,
            )
        )
    return min(upcoming, key=lambda item: item.at, default=None)


def current_window_intakes(
    details: list[IntakeEventDetails],
    medication_sets: list[MedicationSetDetails],
    *,
    now: datetime,
) -> list[IntakeEventDetails]:
    active_sets = {
        regimen.id: item.medication_set
        for item in medication_sets
        if item.medication_set.active
        for regimen in item.regimens
    }
    visible = []
    for item in details:
        event = item.event
        if event.scheduled_at > now:
            continue
        medication_set = active_sets.get(event.regimen_id)
        if medication_set is not None:
            zone = ZoneInfo(medication_set.timezone)
            local_now = now.astimezone(zone)
            scheduled = event.scheduled_at.astimezone(zone)
            if not (
                scheduled.date() == local_now.date()
                and medication_set.window_start <= local_now.time() < medication_set.window_end
                and medication_set.window_start <= scheduled.time() < medication_set.window_end
            ):
                continue
        visible.append(item)
    return visible
