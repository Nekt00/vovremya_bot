from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.methods import DeleteMessage, EditMessageText, SendDocument, SendMessage
from aiogram.methods.base import TelegramMethod, TelegramType
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, TelegramObject, Update
from redis.asyncio import Redis

from medication_reminder.families.service import FamilyChatCleanup


class DeleteIncomingMessageMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        incoming = event.message if isinstance(event, Update) else event
        try:
            return await handler(event, data)
        finally:
            if isinstance(incoming, Message) and incoming.chat.type == "private":
                with suppress(TelegramAPIError):
                    await incoming.delete()


class SingleScreenRequestMiddleware:
    def __init__(self, redis: Redis, *, key_prefix: str = "medication-ui") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    async def __call__(
        self,
        make_request: Callable[[Bot, TelegramMethod[Any]], Awaitable[Any]],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Any:
        if not isinstance(method, SendMessage | SendDocument):
            result = await make_request(bot, method)
            if isinstance(method, EditMessageText) and method.chat_id and method.message_id:
                await self._remember(bot.id, method.chat_id, method.message_id)
            return result

        chat_id = method.chat_id
        is_menu_anchor = isinstance(method, SendMessage) and isinstance(
            method.reply_markup, ReplyKeyboardMarkup
        )
        key = (
            self._menu_message_key(bot.id, chat_id)
            if is_menu_anchor
            else self._message_key(bot.id, chat_id)
        )
        lock = self._redis.lock(f"{key}:lock", timeout=15, blocking_timeout=10)
        async with lock:
            previous = await self._redis.get(key)
            # Deleting a reply-keyboard message can hide the keyboard in Telegram clients.
            # Remove the old anchor before installing its replacement.
            if is_menu_anchor and previous is not None:
                with suppress(TelegramAPIError, ValueError):
                    await make_request(
                        bot,
                        DeleteMessage(chat_id=chat_id, message_id=int(previous)),
                    )
            result = await make_request(bot, method)
            if isinstance(result, Message):
                await self._redis.set(key, str(result.message_id), ex=60 * 60 * 24 * 30)
                if (
                    not is_menu_anchor
                    and previous is not None
                    and previous != str(result.message_id)
                ):
                    with suppress(TelegramAPIError, ValueError):
                        await make_request(
                            bot,
                            DeleteMessage(chat_id=chat_id, message_id=int(previous)),
                        )
            return result

    async def _remember(self, bot_id: int, chat_id: int | str, message_id: int) -> None:
        await self._redis.set(
            self._message_key(bot_id, chat_id),
            str(message_id),
            ex=60 * 60 * 24 * 30,
        )

    def _message_key(self, bot_id: int, chat_id: int | str) -> str:
        return f"{self._key_prefix}:{bot_id}:{chat_id}:last-message"

    def _menu_message_key(self, bot_id: int, chat_id: int | str) -> str:
        return f"{self._key_prefix}:{bot_id}:{chat_id}:menu-message"

    async def refresh_current_screen(
        self,
        bot: Bot,
        *,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
    ) -> None:
        key = self._message_key(bot.id, chat_id)
        async with self._redis.lock(f"{key}:lock", timeout=15, blocking_timeout=5):
            message_id = await self._redis.get(key)
            if message_id is None:
                return
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(message_id),
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )


async def clear_recent_messages(
    bot: Bot,
    *,
    chat_id: int,
    latest_message_id: int,
    limit: int = 500,
) -> None:
    first_message_id = max(1, latest_message_id - limit + 1)
    message_ids = list(range(first_message_id, latest_message_id + 1))
    for offset in range(0, len(message_ids), 100):
        with suppress(TelegramAPIError):
            await bot.delete_messages(
                chat_id=chat_id,
                message_ids=message_ids[offset : offset + 100],
            )


async def delete_family_reminder_messages(
    bot: Bot,
    chats: tuple[FamilyChatCleanup, ...],
) -> None:
    for chat in chats:
        for offset in range(0, len(chat.message_ids), 100):
            with suppress(TelegramAPIError):
                await bot.delete_messages(
                    chat_id=chat.telegram_user_id,
                    message_ids=list(chat.message_ids[offset : offset + 100]),
                )
