from dataclasses import dataclass
from decimal import Decimal

from medication_reminder.intake_events.domain.event import IntakeEvent
from medication_reminder.regimens.domain.regimen import MealTiming, MedicationForm


@dataclass(frozen=True, slots=True)
class IntakeEventDetails:
    event: IntakeEvent
    medication_name: str
    medication_form: MedicationForm
    dose_amount: Decimal
    dose_unit: str
    meal_timing: MealTiming = MealTiming.INDEPENDENT
