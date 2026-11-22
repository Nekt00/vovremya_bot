from asyncio import run
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from medication_reminder.analytics import models as analytics_models  # noqa: F401
from medication_reminder.families import models as family_models  # noqa: F401
from medication_reminder.intake_events.infrastructure import (
    models as intake_event_models,  # noqa: F401
)
from medication_reminder.medication_sets import models as medication_set_models  # noqa: F401
from medication_reminder.regimens.infrastructure import models as regimen_models  # noqa: F401
from medication_reminder.reminders import models as reminder_models  # noqa: F401
from medication_reminder.schedules.infrastructure import models as schedule_models  # noqa: F401
from medication_reminder.shared.config import get_settings
from medication_reminder.shared.database import Base
from medication_reminder.users.infrastructure import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run(run_migrations_online())
