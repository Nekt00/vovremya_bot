from medication_reminder.regimens.domain.regimen import MedicationForm

PRIMARY_STYLE = "primary"
SUCCESS_STYLE = "success"
DANGER_STYLE = "danger"

CALENDAR = "🗓️"
ADD = "➕"
HISTORY = "📊"
SETS = "🗂️"
SETTINGS = "⚙️"
MEDICATION = "💊"
DONE = "✅"
PENDING = "⏳"
SKIPPED = "❌"
SNOOZE = "⏰"
EDIT = "✏️"
DELETE = "🗑️"
BACK = "⬅️"
PAUSE = "⏸️"
RESUME = "▶️"
STOP = "⏹️"
CLOCK = "🕐"
REFRESH = "🔄"

FORM_ICONS: dict[MedicationForm, str] = {
    MedicationForm.TABLET: "⚪️",
    MedicationForm.CAPSULE: MEDICATION,
    MedicationForm.INJECTION: "💉",
    MedicationForm.DROPS: "💧",
    MedicationForm.OTHER: "🩺",
}


def form_icon(form: MedicationForm) -> str:
    return FORM_ICONS[form]
