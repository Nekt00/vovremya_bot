from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from medication_reminder.families.service import FamilyAccessError
from medication_reminder.regimens.application.use_cases import (
    RegimenNotFoundError,
    RegimenUpdateConflictError,
)
from medication_reminder.regimens.domain.regimen import InvalidStatusTransitionError, RegimenStatus
from medication_reminder.telegram.callbacks import RegimenAction, RegimenCallback
from medication_reminder.telegram.keyboards import REGIMENS_BUTTON
from medication_reminder.telegram.regimen_formatting import (
    completion_confirmation,
    deletion_confirmation,
    format_regimen_details,
    format_regimen_list,
)
from medication_reminder.telegram.regimen_service import TelegramRegimenService
from medication_reminder.telegram.screen import answer_main_screen
from medication_reminder.telegram.service import TelegramApplicationService
from medication_reminder.telegram.today import show_today_from_callback
from medication_reminder.telegram.transactions import CommitDatabase


def create_regimen_management_router() -> Router:
    router = Router(name="regimen_management")

    @router.message(Command("regimens"))
    @router.message(F.text == REGIMENS_BUTTON)
    async def regimens(
        message: Message,
        regimen_service: TelegramRegimenService,
    ) -> None:
        if message.from_user is None:
            return
        items = await regimen_service.list_for_user(message.from_user.id)
        text, markup = format_regimen_list(items)
        await answer_main_screen(message, text, markup)

    @router.callback_query(F.data == "rg:list")
    async def regimen_list(
        callback: CallbackQuery,
        regimen_service: TelegramRegimenService,
    ) -> None:
        items = await regimen_service.list_for_user(callback.from_user.id)
        text, markup = format_regimen_list(items)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()

    @router.callback_query(F.data.startswith(f"{RegimenCallback.PREFIX}:"))
    async def regimen_action(
        callback: CallbackQuery,
        state: FSMContext,
        regimen_service: TelegramRegimenService,
        telegram_service: TelegramApplicationService,
        commit_database: CommitDatabase,
    ) -> None:
        response = "Не удалось выполнить действие"
        try:
            parsed = RegimenCallback.decode(callback.data or "")
            details = await regimen_service.details(callback.from_user.id, parsed.regimen_id)
            if parsed.action is not RegimenAction.VIEW and not details.can_manage:
                raise FamilyAccessError("Семейный курс может изменять только владелец группы")
            markup: InlineKeyboardMarkup | None
            return_to_today = False
            if parsed.action is RegimenAction.COMPLETE:
                text, markup = completion_confirmation(details)
            elif parsed.action is RegimenAction.DELETE:
                text, markup = deletion_confirmation(details)
            elif parsed.action is RegimenAction.CONFIRM_DELETE:
                deleted = await regimen_service.delete(
                    callback.from_user.id,
                    parsed.regimen_id,
                )
                await commit_database()
                text, markup = "", None
                return_to_today = True
                response = "Курс удалён" if deleted else "Курс уже удалён"
            else:
                target = {
                    RegimenAction.PAUSE: RegimenStatus.PAUSED,
                    RegimenAction.RESUME: RegimenStatus.ACTIVE,
                    RegimenAction.CONFIRM_COMPLETE: RegimenStatus.COMPLETED,
                }.get(parsed.action)
                if target is not None:
                    details = await regimen_service.change_status(
                        callback.from_user.id,
                        parsed.regimen_id,
                        target,
                    )
                    await commit_database()
                    return_to_today = True
                text, markup = format_regimen_details(details)
            if return_to_today:
                await show_today_from_callback(callback, state, telegram_service)
            elif isinstance(callback.message, Message):
                await callback.message.edit_text(text, reply_markup=markup)
            response = "Готово"
        except RegimenNotFoundError:
            response = "Курс не найден"
        except FamilyAccessError:
            response = "Изменять семейный курс может только владелец группы"
        except (RegimenUpdateConflictError, InvalidStatusTransitionError):
            response = "Состояние уже изменилось — откройте список заново"
        except ValueError:
            response = "Некорректная или устаревшая кнопка"
        finally:
            await callback.answer(response)

    return router
