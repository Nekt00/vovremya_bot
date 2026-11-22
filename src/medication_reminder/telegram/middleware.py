from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medication_reminder.analytics.service import record_activity
from medication_reminder.families.service import FamilyService
from medication_reminder.intake_events.application.use_cases import (
    ListUserIntakeEventDetails,
    TransitionIntakeEvent,
)
from medication_reminder.intake_events.infrastructure.repository import (
    SqlAlchemyIntakeEventRepository,
)
from medication_reminder.medication_sets.application import (
    AddRegimenToMedicationSet,
    CreateMedicationSet,
    DeleteMedicationSet,
    GetMedicationSet,
    ListMedicationSets,
    TakeMedicationSet,
    UpdateMedicationSet,
)
from medication_reminder.medication_sets.repository import SqlAlchemyMedicationSetRepository
from medication_reminder.regimens.application.revisions import ReviseRegimen
from medication_reminder.regimens.application.use_cases import CreateRegimen, ListUserRegimens
from medication_reminder.regimens.infrastructure.repository import SqlAlchemyRegimenRepository
from medication_reminder.regimens.infrastructure.revision_store import (
    SqlAlchemyRegimenRevisionStore,
)
from medication_reminder.schedules.application.use_cases import MaterializeSchedule
from medication_reminder.schedules.infrastructure.repository import (
    SqlAlchemyScheduleMaterializationStore,
)
from medication_reminder.telegram.clock import Clock
from medication_reminder.telegram.medication_set_service import TelegramMedicationSetService
from medication_reminder.telegram.regimen_service import TelegramRegimenService
from medication_reminder.telegram.service import TelegramApplicationService
from medication_reminder.telegram.wizard_service import WizardApplicationService
from medication_reminder.users.application.use_cases import GetOrCreateUser
from medication_reminder.users.infrastructure.repository import SqlAlchemyUserRepository

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DatabaseSessionMiddleware(BaseMiddleware):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Clock,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["database_session"] = session
            event_repository = SqlAlchemyIntakeEventRepository(session)
            user_repository = SqlAlchemyUserRepository(session)
            regimen_repository = SqlAlchemyRegimenRepository(session)
            schedule_store = SqlAlchemyScheduleMaterializationStore(session)
            medication_set_repository = SqlAlchemyMedicationSetRepository(session)
            family_service = FamilyService(
                session,
                GetOrCreateUser(user_repository),
                clock=self._clock,
            )
            data["family_service"] = family_service
            data["commit_database"] = session.commit
            data["telegram_service"] = TelegramApplicationService(
                user_repository,
                ListUserIntakeEventDetails(event_repository),
                TransitionIntakeEvent(event_repository, clock=self._clock),
                clock=self._clock,
                list_medication_sets=ListMedicationSets(medication_set_repository),
            )
            data["regimen_service"] = TelegramRegimenService(
                user_repository,
                regimen_repository,
                schedule_store,
                event_repository,
                ReviseRegimen(SqlAlchemyRegimenRevisionStore(session), clock=self._clock),
                family_service,
                clock=self._clock,
            )
            data["wizard_service"] = WizardApplicationService(
                GetOrCreateUser(user_repository),
                CreateRegimen(regimen_repository, clock=self._clock),
                MaterializeSchedule(
                    schedule_store,
                    clock=self._clock,
                ),
                CreateMedicationSet(medication_set_repository, clock=self._clock),
                AddRegimenToMedicationSet(medication_set_repository),
                family_service,
                clock=self._clock,
            )
            data["medication_set_service"] = TelegramMedicationSetService(
                GetOrCreateUser(user_repository),
                ListUserRegimens(regimen_repository),
                CreateMedicationSet(medication_set_repository, clock=self._clock),
                ListMedicationSets(medication_set_repository),
                TakeMedicationSet(medication_set_repository, clock=self._clock),
                GetMedicationSet(medication_set_repository),
                UpdateMedicationSet(medication_set_repository, clock=self._clock),
                DeleteMedicationSet(medication_set_repository),
                family_service,
            )
            try:
                result = await handler(event, data)
                if isinstance(event, Update):
                    message = event.message or (
                        event.callback_query.message if event.callback_query else None
                    )
                    sender = (
                        event.callback_query.from_user
                        if event.callback_query
                        else event.message.from_user
                        if event.message
                        else None
                    )
                    if isinstance(message, Message) and message.chat.type == "private" and sender:
                        await record_activity(session, sender.id, "bot", self._clock())
            except BaseException:
                await session.rollback()
                raise
            await session.commit()
            return result
