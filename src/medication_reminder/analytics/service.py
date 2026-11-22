from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

STATS_ZONE = ZoneInfo("Europe/Moscow")


async def record_activity(
    session: AsyncSession, telegram_id: int, channel: Literal["bot", "mini_app"], now: datetime
) -> None:
    await session.execute(
        text("""
        INSERT INTO user_activity (user_id, activity_date, channel, last_seen_at)
        SELECT id, :day, :channel, :now FROM users WHERE telegram_user_id = :telegram_id
        ON CONFLICT (user_id, activity_date, channel)
        DO UPDATE SET last_seen_at = GREATEST(user_activity.last_seen_at, EXCLUDED.last_seen_at)
    """),
        {
            "telegram_id": telegram_id,
            "day": now.astimezone(STATS_ZONE).date(),
            "channel": channel,
            "now": now,
        },
    )


async def statistics(session: AsyncSession, days: int, now: datetime) -> str:
    if days not in (1, 7, 30):
        raise ValueError("Unsupported statistics period")
    today = now.astimezone(STATS_ZONE).date()
    start_day = today - timedelta(days=days - 1)
    start = datetime.combine(start_day, time.min, STATS_ZONE)
    params = {"start": start, "now": now, "day": start_day}
    result = (
        (
            await session.execute(
                text("""
        WITH user_setup AS (
          SELECT u.id, u.created_at,
            EXISTS (SELECT 1 FROM regimens r WHERE r.user_id = u.id) AS has_courses,
            EXISTS (SELECT 1 FROM medication_sets s WHERE s.user_id = u.id) AS has_sets,
            EXISTS (SELECT 1 FROM regimens r WHERE r.user_id = u.id
                    AND r.status = 'active') AS has_active_courses
          FROM users u
        )
        SELECT
          (SELECT count(*) FROM users) AS users,
          (SELECT count(*) FROM user_setup WHERE NOT has_courses AND NOT has_sets) AS unconfigured,
          (SELECT count(*) FROM user_setup WHERE NOT has_courses AND has_sets) AS sets_only,
          (SELECT count(*) FROM user_setup WHERE has_courses) AS with_courses,
          (SELECT count(*) FROM user_setup WHERE has_active_courses) AS with_active_courses,
          (SELECT count(*) FROM user_setup WHERE has_sets) AS with_sets,
          (SELECT count(*) FROM user_setup WHERE has_courses
             AND created_at >= :start AND created_at <= :now) AS new_with_courses,
          (SELECT count(DISTINCT user_id) FROM regimens
             WHERE created_at >= :start AND created_at <= :now) AS added_courses,
          (SELECT count(DISTINCT user_id) FROM medication_sets
             WHERE created_at >= :start AND created_at <= :now) AS added_sets,
          (SELECT count(*) FROM users
             WHERE created_at >= :start AND created_at <= :now) AS new_users,
          (SELECT count(*) FROM regimens WHERE status = 'active') AS courses,
          (SELECT count(*) FROM medication_sets) AS sets,
          (SELECT count(*) FROM family_groups) AS families,
          (SELECT count(DISTINCT user_id) FROM user_activity WHERE activity_date >= :day
             AND last_seen_at <= :now) AS active,
          (SELECT count(DISTINCT user_id) FROM user_activity WHERE activity_date >= :day
             AND channel = 'bot' AND last_seen_at <= :now) AS bot,
          (SELECT count(DISTINCT user_id) FROM user_activity WHERE activity_date >= :day
             AND channel = 'mini_app' AND last_seen_at <= :now) AS mini_app
    """),
                params,
            )
        )
        .mappings()
        .one()
    )
    activity = (
        (
            await session.execute(
                text("""
        SELECT h.to_status, count(*) AS n, count(DISTINCT r.user_id) AS people
        FROM intake_event_history h JOIN intake_events e ON e.id = h.event_id
        JOIN regimens r ON r.id = e.regimen_id
        WHERE h.source = 'user' AND h.occurred_at >= :start AND h.occurred_at <= :now
        GROUP BY h.to_status
    """),
                params,
            )
        )
        .mappings()
        .all()
    )
    actions = {row["to_status"]: row["n"] for row in activity}
    people = {row["to_status"]: row["people"] for row in activity}
    reminders = (
        (
            await session.execute(
                text("""
        SELECT
          count(DISTINCT (r.user_id, a.telegram_message_id)) FILTER (
            WHERE a.sent_at >= :start AND a.sent_at <= :now
              AND a.telegram_message_id IS NOT NULL) AS sent,
          count(*) FILTER (WHERE a.status = 'failed' AND a.updated_at >= :start
              AND a.updated_at <= :now) AS failed,
          count(*) FILTER (WHERE a.status = 'abandoned' AND a.updated_at >= :start
              AND a.updated_at <= :now) AS abandoned,
          count(*) FILTER (WHERE a.attempt_count > 1 AND a.updated_at >= :start
              AND a.updated_at <= :now) AS retried
        FROM reminder_attempts a JOIN intake_events e ON e.id = a.event_id
        JOIN regimens r ON r.id = e.regimen_id
    """),
                params,
            )
        )
        .mappings()
        .one()
    )
    return (
        f"📊 <b>Статистика бота · {'Сегодня' if days == 1 else f'{days} дней'}</b>\n"
        f"{start_day:%d.%m.%Y}–{today:%d.%m.%Y} · Москва\n\n"
        f"<b>Пользователи</b>\nВсего: {result['users']}\nНовых за период: {result['new_users']}\n"
        f"Из новых уже с назначениями: {result['new_with_courses']}\n\n"
        f"<b>Настройка аккаунтов · сейчас</b>\n"
        f"Без назначений и наборов: {result['unconfigured']}\n"
        f"Есть только наборы, без назначений: {result['sets_only']}\n"
        f"Есть назначения: {result['with_courses']}\n"
        f"Из них с активными курсами: {result['with_active_courses']}\n"
        f"Всего пользователей с наборами: {result['with_sets']}\n\n"
        f"<b>Использование за период</b>\n"
        f"Активных: {result['active']}\n"
        f"В боте: {result['bot']} · В миниаппе: {result['mini_app']}\n\n"
        f"Пользователей с новыми назначениями: {result['added_courses']}\n"
        f"Пользователей, создавших наборы: {result['added_sets']}\n"
        f"Есть отметки «принято»: у {people.get('taken', 0)} пользователей\n\n"
        f"<b>Сейчас в системе</b>\nАктивных курсов: {result['courses']}\n"
        f"Наборов: {result['sets']} · Семейных групп: {result['families']}\n\n"
        f"<b>Действия с приёмами за период</b>\nПринято: {actions.get('taken', 0)}\n"
        f"Пропущено: {actions.get('skipped', 0)} · Отложено: {actions.get('snoozed', 0)}\n"
        f"Отменено отметок: {actions.get('scheduled', 0)}\n\n"
        f"<b>Уведомления за период</b>\nОтправлено сообщений: {reminders['sent']}\n"
        f"Заданий с ошибкой: {reminders['failed']}\n"
        f"Прекращено попыток: {reminders['abandoned']}\n\n"
        f"Заданий с повторными попытками: {reminders['retried']}\n\n"
        "Активность учитывается с установки обновления. Один человек в обоих каналах "
        "считается одним активным пользователем. Действия учитывают повторные отметки. "
        "Настройка аккаунтов рассчитана по сохранившимся назначениям и наборам, "
        "включая семейные назначения. Удалённые объекты в ней не учитываются. "
        "Отправка означает ответ Telegram API, а не прочтение."
    )
