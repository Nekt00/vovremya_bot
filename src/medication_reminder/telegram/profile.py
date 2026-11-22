import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, InputProfilePhotoStatic
from redis.asyncio import Redis

BOT_NAME = "Вовремя"
BOT_SHORT_DESCRIPTION = (
    "Напоминания о лекарствах и уколах с понятным расписанием и историей приёмов."
)
BOT_DESCRIPTION = (
    "Вовремя помогает соблюдать график лекарств и уколов. "
    "Создавайте назначения и наборы, получайте напоминания и отмечайте фактическое "
    "время приёма. Расписание и история доступны в боте и Mini App."
)

_PROFILE_VERSION = "2026-10-23.1"
_PROFILE_VERSION_KEY = "medication-bot:profile-version"
_DEFAULT_AVATAR_PATH = Path("assets/vovremya-avatar.png")
_logger = logging.getLogger(__name__)


async def sync_bot_profile(
    bot: Bot,
    redis: Redis,
    *,
    avatar_path: Path = _DEFAULT_AVATAR_PATH,
) -> None:
    """Apply the branded Telegram profile once per profile version."""
    if await redis.get(_PROFILE_VERSION_KEY) == _PROFILE_VERSION:
        return
    try:
        await bot.set_my_name(BOT_NAME)
        await bot.set_my_short_description(BOT_SHORT_DESCRIPTION)
        await bot.set_my_description(BOT_DESCRIPTION)
        await bot.set_my_profile_photo(InputProfilePhotoStatic(photo=FSInputFile(avatar_path)))
    except (OSError, TelegramAPIError):
        _logger.exception("Failed to synchronize Telegram bot profile")
        return
    await redis.set(_PROFILE_VERSION_KEY, _PROFILE_VERSION)
