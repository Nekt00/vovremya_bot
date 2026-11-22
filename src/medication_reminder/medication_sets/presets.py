from datetime import time

MEDICATION_SET_PRESETS = {
    "morning": ("Утро", time(6), time(12)),
    "day": ("День", time(11), time(17)),
    "evening": ("Вечер", time(18), time(23)),
}

MEDICATION_SET_EMOJI = {
    "morning": "🌅",
    "day": "☀️",
    "evening": "🌙",
}
