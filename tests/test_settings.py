from pathlib import Path

from pytest import MonkeyPatch

from medication_reminder.shared.config import Settings


def test_settings_use_safe_defaults(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEDICATION_ENVIRONMENT", raising=False)
    monkeypatch.delenv("MEDICATION_DEBUG", raising=False)
    monkeypatch.delenv("MEDICATION_TELEGRAM_BOT_TOKEN", raising=False)

    settings = Settings()

    assert settings.environment == "local"
    assert settings.debug is False
    assert settings.telegram_bot_token is None
