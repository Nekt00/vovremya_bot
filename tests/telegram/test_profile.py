from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from medication_reminder.telegram.profile import (
    BOT_DESCRIPTION,
    BOT_NAME,
    BOT_SHORT_DESCRIPTION,
    sync_bot_profile,
)


@pytest.mark.asyncio
async def test_profile_sync_applies_brand_identity_once(tmp_path: Path) -> None:
    avatar = tmp_path / "avatar.png"
    avatar.write_bytes(b"png")
    bot = SimpleNamespace(
        set_my_name=AsyncMock(),
        set_my_short_description=AsyncMock(),
        set_my_description=AsyncMock(),
        set_my_profile_photo=AsyncMock(),
    )
    redis = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())

    await sync_bot_profile(bot, redis, avatar_path=avatar)  # type: ignore[arg-type]

    bot.set_my_name.assert_awaited_once_with(BOT_NAME)
    bot.set_my_short_description.assert_awaited_once_with(BOT_SHORT_DESCRIPTION)
    bot.set_my_description.assert_awaited_once_with(BOT_DESCRIPTION)
    bot.set_my_profile_photo.assert_awaited_once()
    redis.set.assert_awaited_once()


def test_profile_copy_fits_telegram_limits() -> None:
    assert 1 <= len(BOT_NAME) <= 64
    assert 1 <= len(BOT_SHORT_DESCRIPTION) <= 120
    assert 1 <= len(BOT_DESCRIPTION) <= 512
