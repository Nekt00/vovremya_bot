import asyncio
import logging
from datetime import UTC, datetime, timedelta
from html import escape

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medication_reminder.families.observers import FamilyObserver, observers_for_events
from medication_reminder.reminders.formatting import format_reminder, format_set_reminder
from medication_reminder.reminders.maintenance import (
    cleanup_terminal_reminder_attempts,
    expire_overdue_events,
    extend_open_ended_schedules,
)
from medication_reminder.reminders.repository import (
    ClaimedReminder,
    ClaimedSetReminder,
    SqlAlchemyReminderRepository,
)
from medication_reminder.shared.config import Settings, get_settings
from medication_reminder.shared.database import create_database_engine, create_session_factory
from medication_reminder.shared.dosage import format_dose, meal_timing_suffix
from medication_reminder.telegram.bot import require_bot_token
from medication_reminder.telegram.clean_chat import SingleScreenRequestMiddleware

logger = logging.getLogger(__name__)


async def run_once(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> int:
    async with session_factory() as session, session.begin():
        repository = SqlAlchemyReminderRepository(session)
        now = datetime.now(UTC)
        set_claimed = await repository.claim_set_batch(
            now=now,
            batch_size=settings.reminder_batch_size,
            retry_interval=timedelta(seconds=settings.reminder_retry_interval_seconds),
            claim_timeout=timedelta(seconds=settings.reminder_claim_timeout_seconds),
        )
        claimed = await repository.claim_batch(
            now=now,
            batch_size=max(0, settings.reminder_batch_size - len(set_claimed)),
            retry_interval=timedelta(seconds=settings.reminder_retry_interval_seconds),
            claim_timeout=timedelta(seconds=settings.reminder_claim_timeout_seconds),
        )

    reminders: list[ClaimedSetReminder | ClaimedReminder] = [*set_claimed, *claimed]

    for reminder in reminders:
        async with session_factory() as session, session.begin():
            repository = SqlAlchemyReminderRepository(session)
            deliverable = (
                await repository.is_set_deliverable(
                    reminder.attempt_id,
                    reminder.claim_token,
                    reminder.set_id,
                    tuple(item.event_id for item in reminder.items),
                )
                if isinstance(reminder, ClaimedSetReminder)
                else await repository.is_deliverable(
                    reminder.attempt_id,
                    reminder.claim_token,
                )
            )
            if not deliverable:
                await repository.mark_abandoned(
                    reminder.attempt_id,
                    reminder.claim_token,
                    failed_at=datetime.now(UTC),
                    reason="EventNoLongerDue",
                )
                continue
        try:
            text, keyboard = (
                format_set_reminder(reminder)
                if isinstance(reminder, ClaimedSetReminder)
                else format_reminder(reminder)
            )
            message = await bot.send_message(
                reminder.telegram_user_id,
                text,
                reply_markup=keyboard,
            )
        except (TelegramForbiddenError, TelegramNotFound) as error:
            logger.warning(
                "Reminder delivery permanently unavailable",
                extra=_log_context(reminder),
            )
            async with session_factory() as session, session.begin():
                await SqlAlchemyReminderRepository(session).mark_abandoned(
                    reminder.attempt_id,
                    reminder.claim_token,
                    failed_at=datetime.now(UTC),
                    reason=type(error).__name__,
                )
        except Exception as error:
            logger.exception(
                "Reminder delivery failed",
                extra=_log_context(reminder),
            )
            async with session_factory() as session, session.begin():
                await SqlAlchemyReminderRepository(session).mark_failed(
                    reminder.attempt_id,
                    reminder.claim_token,
                    failed_at=datetime.now(UTC),
                    reason=type(error).__name__,
                )
        else:
            async with session_factory() as session, session.begin():
                await SqlAlchemyReminderRepository(session).mark_sent(
                    reminder.attempt_id,
                    reminder.claim_token,
                    sent_at=datetime.now(UTC),
                    telegram_message_id=message.message_id,
                )
                event_ids = (
                    tuple(item.event_id for item in reminder.items)
                    if isinstance(reminder, ClaimedSetReminder)
                    else (reminder.event_id,)
                )
                observers = await observers_for_events(session, event_ids)
                # shortcut: hold revocation locks during I/O; use an outbox if volume grows.
                await _notify_family_owners(bot, reminder, observers)
    return len(reminders)


async def _notify_family_owners(
    bot: Bot,
    reminder: ClaimedSetReminder | ClaimedReminder,
    observers: list[FamilyObserver],
) -> None:
    grouped: dict[tuple[int, str, str], set[object]] = {}
    for observer in observers:
        key = (
            observer.owner_telegram_user_id,
            observer.group_name,
            observer.recipient_name,
        )
        grouped.setdefault(key, set()).add(observer.event_id)
    for (owner_id, group_name, recipient_name), event_ids in grouped.items():
        if isinstance(reminder, ClaimedSetReminder):
            items = [item for item in reminder.items if item.event_id in event_ids]
            medication_lines = "\n".join(
                f"• <b>{escape(item.medication_name)}</b> — "
                f"{escape(format_dose(item.dose_amount, item.dose_unit))}"
                f"{meal_timing_suffix(item.meal_timing)}"
                for item in items
            )
        else:
            medication_lines = (
                f"• <b>{escape(reminder.medication_name)}</b> — "
                f"{escape(format_dose(reminder.dose_amount, reminder.dose_unit))}"
                f"{meal_timing_suffix(reminder.meal_timing)}"
            )
        text = (
            "👨‍👩‍👧 <b>Семейное напоминание</b>\n\n"
            f"<b>{escape(recipient_name)}</b> · {escape(group_name)}\n"
            f"{medication_lines}\n\n"
            "Статус и фактическое время доступны в разделе «Семья»."
        )
        try:
            await bot.send_message(owner_id, text)
        except (TelegramForbiddenError, TelegramNotFound):
            logger.info("Family observer is unavailable", extra={"owner_id": owner_id})
        except Exception:
            logger.exception("Family reminder delivery failed", extra={"owner_id": owner_id})


async def expire_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory() as session, session.begin():
        return await expire_overdue_events(session, now=datetime.now(UTC))


async def extend_once(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> int:
    async with session_factory() as session, session.begin():
        return await extend_open_ended_schedules(
            session,
            now=datetime.now(UTC),
            horizon_days=settings.schedule_horizon_days,
        )


async def cleanup_once(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> int:
    async with session_factory() as session, session.begin():
        return await cleanup_terminal_reminder_attempts(
            session,
            before=datetime.now(UTC) - timedelta(days=settings.reminder_attempt_retention_days),
        )


def _log_context(reminder: ClaimedSetReminder | ClaimedReminder) -> dict[str, str]:
    if isinstance(reminder, ClaimedSetReminder):
        return {"attempt_id": str(reminder.attempt_id), "set_id": str(reminder.set_id)}
    return {
        "attempt_id": str(reminder.attempt_id),
        "event_id": str(reminder.event_id),
    }


async def run_worker(settings: Settings | None = None) -> None:
    application_settings = settings or get_settings()
    logging.basicConfig(level=application_settings.log_level)
    engine = create_database_engine(
        application_settings.database_url,
        echo=application_settings.debug,
    )
    bot = Bot(
        token=require_bot_token(application_settings.telegram_bot_token),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    clean_chat_redis = Redis.from_url(application_settings.redis_url, decode_responses=True)
    bot.session.middleware.register(SingleScreenRequestMiddleware(clean_chat_redis))
    session_factory = create_session_factory(engine)
    last_expiry_minute: datetime | None = None
    last_extension_date = None
    consecutive_failures = 0
    try:
        while True:
            try:
                current = datetime.now(UTC)
                current_minute = current.replace(second=0, microsecond=0)
                if last_expiry_minute != current_minute:
                    await expire_once(session_factory)
                    last_expiry_minute = current_minute
                if last_extension_date != current.date():
                    await extend_once(session_factory, application_settings)
                    await cleanup_once(session_factory, application_settings)
                    last_extension_date = current.date()
                await run_once(bot, session_factory, application_settings)
            except Exception:
                consecutive_failures += 1
                logger.exception("Reminder worker iteration failed")
                if _should_restart_worker(
                    consecutive_failures,
                    application_settings.reminder_max_consecutive_failures,
                ):
                    logger.critical("Reminder worker failure limit reached; restarting")
                    raise
            else:
                consecutive_failures = 0
            await asyncio.sleep(application_settings.reminder_poll_interval_seconds)
    finally:
        await bot.session.close()
        await clean_chat_redis.aclose()
        await engine.dispose()


def _should_restart_worker(consecutive_failures: int, maximum: int) -> bool:
    return consecutive_failures >= maximum


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
