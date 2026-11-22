from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from medication_reminder.analytics import models as analytics_models
from medication_reminder.families import models as family_models
from medication_reminder.intake_events.infrastructure import models as intake_event_models
from medication_reminder.medication_sets import models as medication_set_models
from medication_reminder.regimens.infrastructure import models as regimen_models
from medication_reminder.reminders import models as reminder_models
from medication_reminder.schedules.infrastructure import models as schedule_models
from medication_reminder.shared.database import Base
from medication_reminder.users.infrastructure import models as user_models

_REGISTERED_MODELS = (
    analytics_models,
    family_models,
    intake_event_models,
    medication_set_models,
    regimen_models,
    reminder_models,
    schedule_models,
    user_models,
)


@pytest_asyncio.fixture(scope="session")
async def postgres_engine() -> AsyncIterator[AsyncEngine]:
    assert _REGISTERED_MODELS
    database_url = os.getenv("MEDICATION_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEDICATION_TEST_DATABASE_URL is not configured")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.fail("MEDICATION_TEST_DATABASE_URL must use postgresql+asyncpg")

    schema = f"test_{uuid4().hex}"
    admin_engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema}},
            poolclass=NullPool,
        )
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            yield engine
        finally:
            await engine.dispose()
    finally:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


@pytest_asyncio.fixture
async def db_session(postgres_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with postgres_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
