from pathlib import Path

import pytest
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage
from aiogram.types import MenuButtonWebApp
from pydantic import SecretStr, ValidationError
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medication_reminder.shared.config import Settings
from medication_reminder.shared.timezones import validate_timezone
from medication_reminder.telegram.bot import (
    BotConfigurationError,
    create_dispatcher,
    require_bot_token,
)
from medication_reminder.telegram.keyboards import (
    TIMEZONE_PRESETS,
    bot_menu_button,
    main_menu,
    settings_keyboard,
    timezone_keyboard,
)


def test_all_timezone_presets_are_valid() -> None:
    assert tuple(validate_timezone(value) for value in TIMEZONE_PRESETS) == TIMEZONE_PRESETS


def test_timezone_keyboard_only_offers_automatic_detection_with_https_url() -> None:
    manual = timezone_keyboard(None)
    automatic = timezone_keyboard("https://example.test/timezone")

    assert all(button.web_app is None for row in manual.inline_keyboard for button in row)
    assert automatic.inline_keyboard[0][0].web_app is not None


def test_main_menu_does_not_duplicate_mini_app_button() -> None:
    keyboard = main_menu()

    assert all(
        button.text != "📱 Открыть приложение" for row in keyboard.keyboard for button in row
    )
    assert [len(row) for row in keyboard.keyboard] == [1, 2, 2, 2]
    assert keyboard.keyboard[0][0].style == "primary"
    assert all(button.style is None for row in keyboard.keyboard[1:] for button in row)
    assert keyboard.is_persistent is True


def test_settings_keyboard_can_return_to_main_menu() -> None:
    keyboard = settings_keyboard(repeat_minutes=30, enabled=True)

    assert keyboard.inline_keyboard[-1][0].callback_data == "nav:today"


def test_bot_menu_opens_current_mini_app_directly() -> None:
    menu = bot_menu_button("https://example.test/mini-app")

    assert isinstance(menu, MenuButtonWebApp)
    assert menu.text == "Открыть Вовремя"
    assert menu.web_app.url == "https://example.test/mini-app"


def test_invalid_mini_app_url_is_rejected(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError, match="HTTPS URL"):
        Settings(telegram_mini_app_url="http://example.test/timezone")


@pytest.mark.parametrize("token", [None, SecretStr(""), SecretStr("   ")])
def test_polling_requires_non_empty_token(token: SecretStr | None) -> None:
    with pytest.raises(BotConfigurationError, match="MEDICATION_TELEGRAM_BOT_TOKEN"):
        require_bot_token(token)


def test_polling_unwraps_secret_token() -> None:
    assert require_bot_token(SecretStr("123:secret")) == "123:secret"


def test_dispatcher_serializes_updates_for_same_fsm_key() -> None:
    dispatcher = create_dispatcher(async_sessionmaker[AsyncSession](), Settings())

    assert isinstance(dispatcher.storage, RedisStorage)
    assert isinstance(dispatcher.fsm.events_isolation, RedisEventIsolation)
