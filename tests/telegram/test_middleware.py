from datetime import UTC, datetime
from typing import Any, cast

import pytest
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medication_reminder.telegram.middleware import DatabaseSessionMiddleware


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.persisted = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1
        self.persisted = True

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self) -> FakeSession:
        return self.session


@pytest.mark.asyncio
async def test_explicit_commit_survives_later_external_failure() -> None:
    session = FakeSession()
    middleware = DatabaseSessionMiddleware(
        cast(async_sessionmaker[AsyncSession], FakeSessionFactory(session)),
        clock=lambda: datetime(2026, 10, 17, tzinfo=UTC),
    )

    async def handler(event: TelegramObject, data: dict[str, Any]) -> None:
        del event
        await data["commit_database"]()
        raise RuntimeError("Telegram edit failed")

    with pytest.raises(RuntimeError, match="Telegram edit failed"):
        await middleware(handler, cast(TelegramObject, object()), {})

    assert session.commits == 1
    assert session.rollbacks == 1
    assert session.persisted
