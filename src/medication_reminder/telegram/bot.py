import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from medication_reminder.shared.config import Settings, get_settings
from medication_reminder.shared.database import create_database_engine, create_session_factory
from medication_reminder.telegram.clean_chat import (
    DeleteIncomingMessageMiddleware,
    SingleScreenRequestMiddleware,
)
from medication_reminder.telegram.clock import Clock, utc_now
from medication_reminder.telegram.family import create_family_router
from medication_reminder.telegram.handlers import (
    _is_private_callback,
    _is_private_message,
    create_clean_chat_router,
    create_router,
)
from medication_reminder.telegram.keyboards import bot_menu_button
from medication_reminder.telegram.medication_sets import create_medication_sets_router
from medication_reminder.telegram.middleware import DatabaseSessionMiddleware
from medication_reminder.telegram.profile import sync_bot_profile
from medication_reminder.telegram.regimen_edit import create_regimen_edit_router
from medication_reminder.telegram.statistics import create_statistics_router
from medication_reminder.telegram.wizard import create_wizard_router


class BotConfigurationError(RuntimeError):
    pass


def require_bot_token(value: SecretStr | None) -> str:
    token = value.get_secret_value().strip() if value is not None else ""
    if not token:
        raise BotConfigurationError(
            "MEDICATION_TELEGRAM_BOT_TOKEN is required to run Telegram polling"
        )
    return token


def create_dispatcher(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    clock: Clock = utc_now,
) -> Dispatcher:
    storage = RedisStorage.from_url(
        settings.redis_url,
        key_builder=DefaultKeyBuilder(prefix="medication-fsm", with_bot_id=True),
    )
    dispatcher = Dispatcher(
        storage=storage,
        events_isolation=storage.create_isolation(lock_kwargs={"timeout": 30}),
    )
    dispatcher.message.filter(_is_private_message)
    dispatcher.callback_query.filter(_is_private_callback)
    dispatcher.update.outer_middleware(DeleteIncomingMessageMiddleware())
    dispatcher.update.outer_middleware(DatabaseSessionMiddleware(session_factory, clock=clock))
    dispatcher.include_router(create_clean_chat_router(mini_app_url=settings.telegram_mini_app_url))
    dispatcher.include_router(create_statistics_router(settings.telegram_admin_ids, clock=clock))
    dispatcher.include_router(create_family_router(mini_app_url=settings.telegram_mini_app_url))
    dispatcher.include_router(create_wizard_router(mini_app_url=settings.telegram_mini_app_url))
    dispatcher.include_router(create_regimen_edit_router())
    dispatcher.include_router(create_medication_sets_router())
    dispatcher.include_router(create_router(mini_app_url=settings.telegram_mini_app_url))
    return dispatcher


async def run_polling(settings: Settings | None = None) -> None:
    application_settings = settings or get_settings()
    token = require_bot_token(application_settings.telegram_bot_token)
    engine: AsyncEngine = create_database_engine(
        application_settings.database_url,
        echo=application_settings.debug,
    )
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    clean_chat_redis = Redis.from_url(application_settings.redis_url, decode_responses=True)
    bot.session.middleware.register(SingleScreenRequestMiddleware(clean_chat_redis))
    dispatcher = create_dispatcher(
        create_session_factory(engine),
        application_settings,
    )
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Открыть главное меню"),
                BotCommand(command="today", description="Приёмы на сегодня"),
                BotCommand(command="add", description="Добавить лекарство или укол"),
                BotCommand(command="regimens", description="Курсы препаратов"),
                BotCommand(command="sets", description="Наборы препаратов"),
                BotCommand(command="history", description="История приёмов"),
                BotCommand(command="settings", description="Настройки напоминаний"),
                BotCommand(command="family", description="Семья и близкие"),
                BotCommand(command="clear", description="Очистить чат и открыть меню"),
            ]
        )
        await bot.set_chat_menu_button(
            menu_button=bot_menu_button(application_settings.telegram_mini_app_url)
        )
        await sync_bot_profile(bot, clean_chat_redis)
        await dispatcher.start_polling(bot, close_bot_session=False)
    finally:
        await bot.session.close()
        await clean_chat_redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
