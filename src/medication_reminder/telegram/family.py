from html import escape
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from medication_reminder.families.service import (
    FamilyAccessError,
    FamilyRole,
    FamilyService,
)
from medication_reminder.shared.dosage import format_dose
from medication_reminder.telegram.callbacks import RegimenAction, RegimenCallback
from medication_reminder.telegram.clean_chat import delete_family_reminder_messages
from medication_reminder.telegram.handlers import TimezoneSetup
from medication_reminder.telegram.keyboards import (
    FAMILY_BUTTON,
    main_menu,
    timezone_keyboard,
)
from medication_reminder.telegram.screen import answer_main_screen
from medication_reminder.telegram.transactions import CommitDatabase
from medication_reminder.telegram.ui import (
    CALENDAR,
    PRIMARY_STYLE,
    REFRESH,
    form_icon,
)


class FamilyInvite(StatesGroup):
    group_name = State()
    display_name = State()
    role = State()


class FamilyManage(StatesGroup):
    rename_group = State()
    rename_member = State()


def create_family_router(*, mini_app_url: str | None) -> Router:
    router = Router(name="family")

    @router.message(CommandStart(deep_link=True))
    async def accept_invite(
        message: Message,
        command: CommandObject,
        state: FSMContext,
        family_service: FamilyService,
        commit_database: CommitDatabase,
    ) -> None:
        args = command.args or ""
        if not args.startswith("family_"):
            return
        await state.clear()
        try:
            accepted = await family_service.accept_invitation(
                message.from_user.id if message.from_user else 0,
                args.removeprefix("family_"),
            )
            await commit_database()
            text = (
                "👨‍👩‍👧 <b>Семейный доступ подключён</b>\n\n"
                f"Вы добавлены как <b>{escape(accepted.display_name)}</b> "
                f"в группу «<b>{escape(accepted.group_name)}</b>».\n"
                "Созданные для вас курсы появятся в разделе «Сегодня» и в приложении."
            )
            text += (
                "\nРоль: <b>только отмечать приёмы</b>."
                if accepted.role == "dependent"
                else "\nРоль: <b>можно добавлять свои курсы</b>."
            )
            if not accepted.timezone_configured:
                text += (
                    "\n\nЧтобы владелец мог создать первый курс, выберите ваш часовой пояс."
                )
                await state.set_state(TimezoneSetup.waiting_for_iana)
                await message.answer(text, reply_markup=timezone_keyboard(mini_app_url))
                return
        except FamilyAccessError as error:
            text = f"Не удалось принять приглашение: {escape(str(error))}."
        await message.answer(text, reply_markup=main_menu())

    @router.message(Command("family"))
    @router.message(F.text == FAMILY_BUTTON)
    async def family_home(message: Message, family_service: FamilyService) -> None:
        await _show_family(message, family_service)

    @router.callback_query(F.data == "family:home")
    async def family_home_callback(callback: CallbackQuery, family_service: FamilyService) -> None:
        if isinstance(callback.message, Message):
            text, markup = await _family_view(callback.from_user.id, family_service)
            await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()

    @router.callback_query(F.data == "family:invite")
    async def begin_invite(
        callback: CallbackQuery,
        state: FSMContext,
        family_service: FamilyService,
    ) -> None:
        groups = await family_service.list_owned_groups(callback.from_user.id)
        await state.clear()
        if isinstance(callback.message, Message):
            if not groups:
                await state.set_state(FamilyInvite.group_name)
                await callback.message.edit_text(
                    "👨‍👩‍👧 <b>Новая группа</b>\n\n"
                    "Введите название, например <i>Семья</i> или <i>Мама и папа</i>."
                )
            else:
                rows = [
                    [
                        InlineKeyboardButton(
                            text=f"👨‍👩‍👧 {group.name}"[:64],
                            callback_data=f"family:invite:group:{group.id}",
                        )
                    ]
                    for group in groups
                ]
                rows.append(
                    [
                        InlineKeyboardButton(
                            text="➕ Новая группа",
                            callback_data="family:invite:new",
                        )
                    ]
                )
                await callback.message.edit_text(
                    "👨‍👩‍👧 <b>Куда добавить участника?</b>",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                )
        await callback.answer()

    @router.callback_query(F.data == "family:invite:new")
    async def invite_new_group(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(FamilyInvite.group_name)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "👨‍👩‍👧 <b>Новая группа</b>\n\nВведите название группы."
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("fg:ren:"))
    async def begin_rename_group(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            group_id = _callback_uuid(callback.data, "fg:ren:")
        except ValueError:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        await state.clear()
        await state.update_data(family_group_id=str(group_id))
        await state.set_state(FamilyManage.rename_group)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "✏️ <b>Переименование группы</b>\n\nВведите новое название."
            )
        await callback.answer()

    @router.message(FamilyManage.rename_group)
    async def rename_group(
        message: Message,
        state: FSMContext,
        family_service: FamilyService,
        commit_database: CommitDatabase,
    ) -> None:
        data = await state.get_data()
        try:
            await family_service.rename_group(
                message.from_user.id if message.from_user else 0,
                group_id=UUID(str(data["family_group_id"])),
                name=message.text or "",
            )
            await commit_database()
        except (FamilyAccessError, KeyError, ValueError) as error:
            await message.answer(f"Не удалось переименовать группу: {escape(str(error))}")
            return
        await state.clear()
        await _show_family(message, family_service)

    @router.callback_query(F.data.startswith("fm:ren:"))
    async def begin_rename_member(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            member_id = _callback_uuid(callback.data, "fm:ren:")
        except ValueError:
            await callback.answer("Участник не найден", show_alert=True)
            return
        await state.clear()
        await state.update_data(family_member_id=str(member_id))
        await state.set_state(FamilyManage.rename_member)
        if isinstance(callback.message, Message):
            await callback.message.edit_text("✏️ <b>Имя участника</b>\n\nВведите новое имя.")
        await callback.answer()

    @router.message(FamilyManage.rename_member)
    async def rename_member(
        message: Message,
        state: FSMContext,
        family_service: FamilyService,
        commit_database: CommitDatabase,
    ) -> None:
        data = await state.get_data()
        try:
            await family_service.rename_member(
                message.from_user.id if message.from_user else 0,
                member_id=UUID(str(data["family_member_id"])),
                display_name=message.text or "",
            )
            await commit_database()
        except (FamilyAccessError, KeyError, ValueError) as error:
            await message.answer(f"Не удалось переименовать участника: {escape(str(error))}")
            return
        await state.clear()
        await _show_family(message, family_service)

    @router.callback_query(F.data.startswith("fg:askdel:"))
    async def ask_delete_group(callback: CallbackQuery) -> None:
        try:
            group_id = _callback_uuid(callback.data, "fg:askdel:")
        except ValueError:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Удалить группу вместе с участниками и семейными курсами?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🗑️ Удалить группу",
                                callback_data=f"fg:del:{group_id}",
                            )
                        ],
                        [InlineKeyboardButton(text="← Назад", callback_data="family:home")],
                    ]
                ),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("fg:del:"))
    async def delete_group(
        callback: CallbackQuery,
        bot: Bot,
        family_service: FamilyService,
        commit_database: CommitDatabase,
    ) -> None:
        try:
            removed = await family_service.delete_group(
                callback.from_user.id,
                group_id=_callback_uuid(callback.data, "fg:del:"),
            )
            await commit_database()
            await delete_family_reminder_messages(bot, removed.chats)
        except (FamilyAccessError, ValueError) as error:
            await callback.answer(str(error), show_alert=True)
            return
        await _refresh_family_callback(callback, family_service)
        await callback.answer("Группа удалена")

    @router.callback_query(F.data.startswith("fm:askdel:"))
    async def ask_delete_member(callback: CallbackQuery) -> None:
        try:
            member_id = _callback_uuid(callback.data, "fm:askdel:")
        except ValueError:
            await callback.answer("Участник не найден", show_alert=True)
            return
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Удалить участника и все созданные для него семейные курсы?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🗑️ Удалить участника",
                                callback_data=f"fm:del:{member_id}",
                            )
                        ],
                        [InlineKeyboardButton(text="← Назад", callback_data="family:home")],
                    ]
                ),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("fm:del:"))
    async def delete_member(
        callback: CallbackQuery,
        bot: Bot,
        family_service: FamilyService,
        commit_database: CommitDatabase,
    ) -> None:
        try:
            removed = await family_service.remove_member(
                callback.from_user.id,
                member_id=_callback_uuid(callback.data, "fm:del:"),
            )
            await commit_database()
            await delete_family_reminder_messages(bot, removed.chats)
        except (FamilyAccessError, ValueError) as error:
            await callback.answer(str(error), show_alert=True)
            return
        await _refresh_family_callback(callback, family_service)
        await callback.answer("Участник удалён")

    @router.callback_query(F.data.startswith("family:invite:group:"))
    async def invite_existing_group(callback: CallbackQuery, state: FSMContext) -> None:
        group_id = (callback.data or "").removeprefix("family:invite:group:")
        try:
            UUID(group_id)
        except ValueError:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        await state.update_data(family_group_id=group_id)
        await state.set_state(FamilyInvite.display_name)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "Как называть участника внутри группы? Например: <i>Мама</i>, <i>Саша</i>."
            )
        await callback.answer()

    @router.message(FamilyInvite.group_name)
    async def invite_group_name(message: Message, state: FSMContext) -> None:
        value = " ".join((message.text or "").split())
        if not 1 <= len(value) <= 64:
            await message.answer("Введите название группы длиной от 1 до 64 символов.")
            return
        await state.update_data(family_group_name=value)
        await state.set_state(FamilyInvite.display_name)
        await message.answer(
            "Как называть участника внутри группы? Например: <i>Мама</i>, <i>Саша</i>."
        )

    @router.message(FamilyInvite.display_name)
    async def invite_display_name(
        message: Message,
        state: FSMContext,
    ) -> None:
        display_name = " ".join((message.text or "").split())
        if not 1 <= len(display_name) <= 64:
            await message.answer("Введите имя участника длиной от 1 до 64 символов.")
            return
        await state.update_data(family_display_name=display_name)
        await state.set_state(FamilyInvite.role)
        await message.answer(
            "Что сможет делать участник?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Только отмечать приёмы",
                            callback_data="family:invite:role:dependent",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="➕ Отмечать и добавлять свои",
                            callback_data="family:invite:role:self_managed",
                        )
                    ],
                ]
            ),
        )

    @router.callback_query(FamilyInvite.role, F.data.startswith("family:invite:role:"))
    async def invite_role(
        callback: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        family_service: FamilyService,
        commit_database: CommitDatabase,
    ) -> None:
        role_value = (callback.data or "").removeprefix("family:invite:role:")
        if role_value not in {"dependent", "self_managed"}:
            await callback.answer("Неизвестная роль", show_alert=True)
            return
        role: FamilyRole = "dependent" if role_value == "dependent" else "self_managed"
        data = await state.get_data()
        try:
            invitation = await family_service.create_invitation(
                callback.from_user.id,
                group_name=(
                    str(data["family_group_name"]) if data.get("family_group_name") else None
                ),
                group_id=(
                    UUID(str(data["family_group_id"])) if data.get("family_group_id") else None
                ),
                display_name=str(data["family_display_name"]),
                role=role,
            )
            await commit_database()
        except (FamilyAccessError, KeyError) as error:
            await callback.answer(f"Не удалось создать приглашение: {error}", show_alert=True)
            return
        await state.clear()
        username = (await bot.get_me()).username
        link = f"https://t.me/{username}?start=family_{invitation.token}"
        role_label = (
            "Только отмечать приёмы"
            if invitation.role == "dependent"
            else "Отмечать и добавлять свои"
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "✅ <b>Приглашение готово</b>\n\n"
                f"Группа: <b>{escape(invitation.group_name)}</b>\n"
                f"Участник: <b>{escape(invitation.display_name)}</b>\n"
                f"Роль: <b>{role_label}</b>\n"
                f"Действует до: <b>{invitation.expires_at:%d.%m.%Y %H:%M} UTC</b>\n\n"
                "Отправьте эту одноразовую ссылку участнику:\n"
                f'<a href="{escape(link)}">Открыть приглашение</a>\n'
                f"<code>{escape(link)}</code>",
            )
        await callback.answer("Приглашение создано")

    return router


async def _show_family(message: Message, family_service: FamilyService) -> None:
    if message.from_user is None:
        return
    text, markup = await _family_view(message.from_user.id, family_service)
    await answer_main_screen(message, text, markup)


async def _family_view(
    telegram_user_id: int, family_service: FamilyService
) -> tuple[str, InlineKeyboardMarkup]:
    groups = await family_service.list_owned_groups(telegram_user_id)
    statuses = await family_service.today_statuses(telegram_user_id)
    assignments = await family_service.list_owned_assignments(telegram_user_id)
    lines = ["👨‍👩‍👧 <b>Семья</b>"]
    if groups:
        lines.append("")
        for group in groups:
            members = ", ".join(escape(item.display_name) for item in group.members)
            lines.append(f"<b>{escape(group.name)}</b>: {members or 'пока без участников'}")
    else:
        lines.extend(
            [
                "",
                "Создайте группу и пригласите близкого. После принятия ссылки вы сможете "
                "создавать для него курсы.",
            ]
        )
    if statuses:
        completed = sum(item.status == "taken" for item in statuses)
        lines.extend(
            [
                "",
                "<b>Сегодня у близких</b>",
                f"Выполнено: <b>{completed}</b> из <b>{len(statuses)}</b>",
                "",
            ]
        )
        icons = {
            "taken": "✅",
            "skipped": "⏭",
            "missed": "⚠️",
            "cancelled": "✖️",
            "due": "🔔",
            "snoozed": "⏰",
            "scheduled": "○",
        }
        for status_item in statuses:
            local_scheduled = status_item.scheduled_at.astimezone(ZoneInfo(status_item.timezone))
            resolved = ""
            if status_item.resolved_at is not None:
                local_resolved = status_item.resolved_at.astimezone(ZoneInfo(status_item.timezone))
                resolved = f" · отмечено {local_resolved:%H:%M}"
            lines.append(
                f"{icons.get(status_item.status, '○')} "
                f"<b>{escape(status_item.display_name)}</b> · "
                f"{local_scheduled:%H:%M} · {escape(status_item.medication_name)} "
                f"{escape(format_dose(status_item.dose_amount, status_item.dose_unit))}"
                f"{resolved}"
            )
    elif groups:
        lines.extend(["", "На сегодня по семейным курсам приёмов нет."])
    rows: list[list[InlineKeyboardButton]] = []
    for group in groups:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ {group.name}"[:64],
                    callback_data=f"fg:ren:{group.id}",
                ),
                InlineKeyboardButton(text="🗑️ Группа", callback_data=f"fg:askdel:{group.id}"),
            ]
        )
        for member in group.members:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"✏️ {member.display_name}"[:64],
                        callback_data=f"fm:ren:{member.member_id}",
                    ),
                    InlineKeyboardButton(
                        text="🗑️ Участник",
                        callback_data=f"fm:askdel:{member.member_id}",
                    ),
                ]
            )
    if assignments:
        lines.extend(["", "<b>Курсы</b>"])
        for assignment in assignments[:20]:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=(
                            f"{form_icon(assignment.medication_form)} "
                            f"{assignment.medication_name} · {assignment.display_name}"
                        )[:64],
                        callback_data=RegimenCallback(
                            assignment.regimen_id, RegimenAction.VIEW
                        ).encode(),
                    )
                ]
            )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="➕ Пригласить близкого",
                    callback_data="family:invite",
                    style=PRIMARY_STYLE,
                )
            ],
            [
                InlineKeyboardButton(text=f"{REFRESH} Обновить", callback_data="family:home"),
                InlineKeyboardButton(text=f"{CALENDAR} Сегодня", callback_data="nav:today"),
            ],
        ]
    )
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _callback_uuid(data: str | None, prefix: str) -> UUID:
    return UUID((data or "").removeprefix(prefix))


async def _refresh_family_callback(
    callback: CallbackQuery,
    family_service: FamilyService,
) -> None:
    if isinstance(callback.message, Message):
        text, markup = await _family_view(callback.from_user.id, family_service)
        await callback.message.edit_text(text, reply_markup=markup)
