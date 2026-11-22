# ruff: noqa: RUF001
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.analytics.models import UserActivityModel
from medication_reminder.analytics.service import record_activity, statistics
from medication_reminder.users.infrastructure.models import UserModel

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_activity_is_unique_across_channels_and_excludes_old_days(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 11, 3, 21, 30, tzinfo=UTC)  # November 4 in Moscow.
    first, second = uuid4(), uuid4()
    db_session.add_all(
        [
            UserModel(id=first, telegram_user_id=91001, created_at=now, updated_at=now),
            UserModel(id=second, telegram_user_id=91002, created_at=now, updated_at=now),
        ]
    )
    await db_session.flush()
    await record_activity(db_session, 91001, "bot", now)
    await record_activity(db_session, 91001, "bot", now)
    await record_activity(db_session, 91001, "mini_app", now)
    await record_activity(db_session, 91002, "bot", now - timedelta(days=2))
    await record_activity(db_session, 99999, "bot", now)  # Unknown users are not registered.
    assert await db_session.scalar(select(func.count()).select_from(UserActivityModel)) == 3
    text = await statistics(db_session, 1, now)
    assert "04.11.2026" in text
    assert "Активных: 1" in text
    assert "В боте: 1 · В миниаппе: 1" in text
    assert "Активных: 2" in await statistics(db_session, 7, now)
    user = await db_session.get(UserModel, first)
    assert user is not None
    await db_session.delete(user)
    await db_session.flush()
    assert await db_session.scalar(select(func.count()).select_from(UserActivityModel)) == 1


@pytest.mark.asyncio
async def test_statistics_distinguishes_empty_accounts_sets_and_courses(
    db_session: AsyncSession,
) -> None:
    from datetime import time
    from decimal import Decimal

    from medication_reminder.medication_sets.models import MedicationSetModel
    from medication_reminder.regimens.infrastructure.models import RegimenModel

    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    empty, sets_only, configured, completed = [uuid4() for _ in range(4)]
    db_session.add_all(
        [
            UserModel(
                id=user_id,
                telegram_user_id=92001 + index,
                created_at=now if index < 3 else now - timedelta(days=10),
                updated_at=now,
            )
            for index, user_id in enumerate((empty, sets_only, configured, completed))
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            MedicationSetModel(
                id=uuid4(),
                user_id=user_id,
                name=name,
                window_start=time(6),
                window_end=time(12),
                timezone="Europe/Moscow",
                active=True,
                created_at=now,
                updated_at=now,
            )
            for user_id, name in ((sets_only, "Утро"), (configured, "Утро"), (configured, "День"))
        ]
    )
    db_session.add_all(
        [
            RegimenModel(
                id=uuid4(),
                user_id=user_id,
                medication_name="Test",
                medication_form="tablet",
                dose_amount=Decimal("1"),
                dose_unit="табл.",
                start_date=now.date(),
                status=status,
                created_at=now if status == "active" else now - timedelta(days=10),
                updated_at=now,
            )
            for user_id, status in (
                (configured, "active"),
                (configured, "active"),
                (completed, "completed"),
            )
        ]
    )
    await db_session.flush()
    report = await statistics(db_session, 1, now)
    for line in (
        "Всего: 4",
        "Новых за период: 3",
        "Из новых уже с назначениями: 1",
        "Без назначений и наборов: 1",
        "Есть только наборы, без назначений: 1",
        "Есть назначения: 2",
        "Из них с активными курсами: 1",
        "Всего пользователей с наборами: 2",
        "Пользователей с новыми назначениями: 1",
        "Пользователей, создавших наборы: 2",
    ):
        assert line in report
    assert "Из новых уже с назначениями: 2" in await statistics(db_session, 30, now)
