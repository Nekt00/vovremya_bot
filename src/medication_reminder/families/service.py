from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from medication_reminder.families.models import (
    FamilyGroupModel,
    FamilyInvitationModel,
    FamilyMemberModel,
    FamilyRegimenAssignmentModel,
)
from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.regimens.domain.regimen import MedicationForm
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.reminders.models import ReminderAttemptModel
from medication_reminder.users.application.use_cases import GetOrCreateUser
from medication_reminder.users.infrastructure.models import UserModel

INVITATION_LIFETIME = timedelta(days=7)
FamilyRole = Literal["dependent", "self_managed"]
FAMILY_ROLES = {"dependent", "self_managed"}


class FamilyAccessError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FamilyTarget:
    user_id: UUID
    telegram_user_id: int
    group_id: UUID
    group_name: str
    display_name: str
    timezone: str | None
    member_id: UUID
    role: FamilyRole


@dataclass(frozen=True, slots=True)
class FamilyGroupSummary:
    id: UUID
    name: str
    members: tuple[FamilyTarget, ...]


@dataclass(frozen=True, slots=True)
class CreatedInvitation:
    token: str
    group_name: str
    display_name: str
    expires_at: datetime
    role: FamilyRole


@dataclass(frozen=True, slots=True)
class AcceptedInvitation:
    group_name: str
    display_name: str
    timezone_configured: bool
    role: FamilyRole


@dataclass(frozen=True, slots=True)
class FamilyIntakeStatus:
    display_name: str
    group_name: str
    medication_name: str
    dose_amount: Decimal
    dose_unit: str
    scheduled_at: datetime
    timezone: str
    status: str
    resolved_at: datetime | None


@dataclass(frozen=True, slots=True)
class FamilyAssignmentSummary:
    regimen_id: UUID
    group_name: str
    display_name: str
    medication_name: str
    medication_form: MedicationForm
    status: str


@dataclass(frozen=True, slots=True)
class FamilyChatCleanup:
    telegram_user_id: int
    message_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RemovedFamilyAccess:
    chats: tuple[FamilyChatCleanup, ...]


class FamilyService:
    def __init__(
        self,
        session: AsyncSession,
        get_or_create_user: GetOrCreateUser,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session = session
        self._get_or_create_user = get_or_create_user
        self._clock = clock

    async def create_invitation(
        self,
        owner_telegram_id: int,
        *,
        group_name: str | None = None,
        group_id: UUID | None = None,
        display_name: str,
        role: FamilyRole = "self_managed",
    ) -> CreatedInvitation:
        owner = await self._get_or_create_user(owner_telegram_id)
        display_name = _clean_name(display_name, "Имя участника")
        if role not in FAMILY_ROLES:
            raise FamilyAccessError("Неизвестная роль участника")
        group: FamilyGroupModel
        if group_id is not None:
            group = await self._owned_group(owner.id, group_id)
        else:
            if group_name is None:
                raise FamilyAccessError("Выберите группу")
            group_name = _clean_name(group_name, "Название группы")
            normalized = group_name.casefold()
            created_group = (
                await self._session.scalars(
                    insert(FamilyGroupModel)
                    .values(
                        id=uuid4(),
                        owner_user_id=owner.id,
                        name=group_name,
                        normalized_name=normalized,
                        created_at=self._clock(),
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            FamilyGroupModel.owner_user_id,
                            FamilyGroupModel.normalized_name,
                        ]
                    )
                    .returning(FamilyGroupModel)
                )
            ).one_or_none()
            if created_group is None:
                group = (
                    await self._session.scalars(
                        select(FamilyGroupModel).where(
                            FamilyGroupModel.owner_user_id == owner.id,
                            FamilyGroupModel.normalized_name == normalized,
                        )
                    )
                ).one()
            else:
                group = created_group

        token = secrets.token_urlsafe(24)
        now = self._clock()
        expires_at = now + INVITATION_LIFETIME
        self._session.add(
            FamilyInvitationModel(
                id=uuid4(),
                group_id=group.id,
                invited_by_user_id=owner.id,
                display_name=display_name,
                role=role,
                token_hash=_token_hash(token),
                expires_at=expires_at,
                accepted_by_user_id=None,
                accepted_at=None,
                created_at=now,
            )
        )
        await self._session.flush()
        return CreatedInvitation(token, group.name, display_name, expires_at, role)

    async def accept_invitation(self, telegram_user_id: int, token: str) -> AcceptedInvitation:
        user = await self._get_or_create_user(telegram_user_id)
        now = self._clock()
        invitation = (
            await self._session.scalars(
                select(FamilyInvitationModel)
                .where(FamilyInvitationModel.token_hash == _token_hash(token))
                .with_for_update()
            )
        ).one_or_none()
        if invitation is None:
            raise FamilyAccessError("Ссылка приглашения недействительна")
        if invitation.accepted_at is not None:
            raise FamilyAccessError("Это приглашение уже использовано")
        if invitation.expires_at <= now:
            raise FamilyAccessError("Срок действия приглашения истёк")
        group = await self._session.get(FamilyGroupModel, invitation.group_id)
        if group is None:
            raise FamilyAccessError("Группа больше не существует")
        if group.owner_user_id == user.id:
            raise FamilyAccessError("Владелец уже состоит в этой группе")
        existing = (
            await self._session.scalars(
                select(FamilyMemberModel).where(
                    FamilyMemberModel.group_id == group.id,
                    FamilyMemberModel.user_id == user.id,
                )
            )
        ).one_or_none()
        if existing is None:
            self._session.add(
                FamilyMemberModel(
                    id=uuid4(),
                    group_id=group.id,
                    user_id=user.id,
                    display_name=invitation.display_name,
                    role=invitation.role,
                    joined_at=now,
                )
            )
        else:
            existing.display_name = invitation.display_name
            existing.role = invitation.role
        invitation.accepted_by_user_id = user.id
        invitation.accepted_at = now
        await self._session.flush()
        return AcceptedInvitation(
            group.name,
            invitation.display_name,
            timezone_configured=user.timezone is not None,
            role=cast(FamilyRole, invitation.role),
        )

    async def list_owned_groups(self, owner_telegram_id: int) -> list[FamilyGroupSummary]:
        owner = await self._get_or_create_user(owner_telegram_id)
        rows = (
            await self._session.execute(
                select(FamilyGroupModel, FamilyMemberModel, UserModel)
                .outerjoin(FamilyMemberModel, FamilyMemberModel.group_id == FamilyGroupModel.id)
                .outerjoin(UserModel, UserModel.id == FamilyMemberModel.user_id)
                .where(FamilyGroupModel.owner_user_id == owner.id)
                .order_by(FamilyGroupModel.created_at, FamilyMemberModel.joined_at)
            )
        ).all()
        groups: dict[UUID, tuple[FamilyGroupModel, list[FamilyTarget]]] = {}
        for group, member, user in rows:
            entry = groups.setdefault(group.id, (group, []))
            if member is not None and user is not None:
                entry[1].append(
                    FamilyTarget(
                        user.id,
                        user.telegram_user_id,
                        group.id,
                        group.name,
                        member.display_name,
                        user.timezone,
                        member.id,
                        cast(FamilyRole, member.role),
                    )
                )
        return [
            FamilyGroupSummary(group.id, group.name, tuple(members))
            for group, members in groups.values()
        ]

    async def list_targets(self, owner_telegram_id: int) -> list[FamilyTarget]:
        return [
            member
            for group in await self.list_owned_groups(owner_telegram_id)
            for member in group.members
        ]

    async def rename_group(
        self,
        owner_telegram_id: int,
        *,
        group_id: UUID,
        name: str,
    ) -> None:
        owner = await self._get_or_create_user(owner_telegram_id)
        group = await self._owned_group(owner.id, group_id)
        name = _clean_name(name, "Название группы")
        normalized = name.casefold()
        duplicate = (
            await self._session.scalars(
                select(FamilyGroupModel.id).where(
                    FamilyGroupModel.owner_user_id == owner.id,
                    FamilyGroupModel.normalized_name == normalized,
                    FamilyGroupModel.id != group.id,
                )
            )
        ).one_or_none()
        if duplicate is not None:
            raise FamilyAccessError("Такое название группы уже используется")
        group.name = name
        group.normalized_name = normalized
        await self._session.flush()

    async def rename_member(
        self,
        owner_telegram_id: int,
        *,
        member_id: UUID,
        display_name: str,
    ) -> None:
        owner = await self._get_or_create_user(owner_telegram_id)
        member, _user = await self._owned_member(owner.id, member_id)
        member.display_name = _clean_name(display_name, "Имя участника")
        await self._session.flush()

    async def remove_member(
        self,
        owner_telegram_id: int,
        *,
        member_id: UUID,
    ) -> RemovedFamilyAccess:
        owner = await self._get_or_create_user(owner_telegram_id)
        member, user = await self._owned_member(owner.id, member_id)
        cleanup = await self._remove_assignments(
            FamilyRegimenAssignmentModel.group_id == member.group_id,
            FamilyRegimenAssignmentModel.recipient_user_id == member.user_id,
        )
        await self._session.delete(member)
        await self._session.flush()
        return RemovedFamilyAccess(
            (FamilyChatCleanup(user.telegram_user_id, cleanup.get(user.id, ())),)
        )

    async def delete_group(
        self,
        owner_telegram_id: int,
        *,
        group_id: UUID,
    ) -> RemovedFamilyAccess:
        owner = await self._get_or_create_user(owner_telegram_id)
        group = await self._owned_group(owner.id, group_id)
        members = (
            await self._session.execute(
                select(FamilyMemberModel, UserModel)
                .join(UserModel, UserModel.id == FamilyMemberModel.user_id)
                .where(FamilyMemberModel.group_id == group.id)
            )
        ).all()
        cleanup = await self._remove_assignments(FamilyRegimenAssignmentModel.group_id == group.id)
        await self._session.delete(group)
        await self._session.flush()
        return RemovedFamilyAccess(
            tuple(
                FamilyChatCleanup(user.telegram_user_id, cleanup.get(member.user_id, ()))
                for member, user in members
            )
        )

    async def remove_owned_assignments_for_account_deletion(
        self, owner_telegram_id: int
    ) -> RemovedFamilyAccess:
        owner = (
            await self._session.scalars(
                select(UserModel)
                .where(UserModel.telegram_user_id == owner_telegram_id)
                .with_for_update()
            )
        ).one_or_none()
        if owner is None:
            return RemovedFamilyAccess(())
        cleanup = await self._remove_assignments(
            FamilyRegimenAssignmentModel.assigned_by_user_id == owner.id
        )
        if not cleanup:
            return RemovedFamilyAccess(())
        users = (
            await self._session.scalars(select(UserModel).where(UserModel.id.in_(cleanup)))
        ).all()
        return RemovedFamilyAccess(
            tuple(FamilyChatCleanup(user.telegram_user_id, cleanup[user.id]) for user in users)
        )

    async def resolve_target(
        self,
        owner_telegram_id: int,
        *,
        target_user_id: UUID,
        group_id: UUID,
    ) -> FamilyTarget:
        owner = await self._get_or_create_user(owner_telegram_id)
        row = (
            await self._session.execute(
                select(FamilyGroupModel, FamilyMemberModel, UserModel)
                .join(FamilyMemberModel, FamilyMemberModel.group_id == FamilyGroupModel.id)
                .join(UserModel, UserModel.id == FamilyMemberModel.user_id)
                .where(
                    FamilyGroupModel.id == group_id,
                    FamilyGroupModel.owner_user_id == owner.id,
                    FamilyMemberModel.user_id == target_user_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise FamilyAccessError("Участник больше недоступен")
        group, member, user = row
        return FamilyTarget(
            user.id,
            user.telegram_user_id,
            group.id,
            group.name,
            member.display_name,
            user.timezone,
            member.id,
            cast(FamilyRole, member.role),
        )

    async def can_manage_personal_regimens(self, telegram_user_id: int) -> bool:
        user = await self._get_or_create_user(telegram_user_id)
        roles = (
            await self._session.scalars(
                select(FamilyMemberModel.role).where(FamilyMemberModel.user_id == user.id)
            )
        ).all()
        return "dependent" not in roles

    async def ensure_can_manage_personal_regimens(self, telegram_user_id: int) -> None:
        if not await self.can_manage_personal_regimens(telegram_user_id):
            raise FamilyAccessError("Ваша роль разрешает только отмечать назначенные приёмы")

    async def record_assignment(
        self,
        *,
        regimen_id: UUID,
        owner_telegram_id: int,
        target_user_id: UUID,
        group_id: UUID,
    ) -> None:
        owner = await self._get_or_create_user(owner_telegram_id)
        await self.resolve_target(
            owner_telegram_id, target_user_id=target_user_id, group_id=group_id
        )
        self._session.add(
            FamilyRegimenAssignmentModel(
                regimen_id=regimen_id,
                group_id=group_id,
                assigned_by_user_id=owner.id,
                recipient_user_id=target_user_id,
                created_at=self._clock(),
            )
        )
        await self._session.flush()

    async def today_statuses(self, owner_telegram_id: int) -> list[FamilyIntakeStatus]:
        owner = await self._get_or_create_user(owner_telegram_id)
        now = self._clock()
        rows = (
            await self._session.execute(
                select(
                    FamilyGroupModel,
                    FamilyMemberModel,
                    IntakeEventModel,
                )
                .join(
                    FamilyRegimenAssignmentModel,
                    FamilyRegimenAssignmentModel.group_id == FamilyGroupModel.id,
                )
                .join(
                    FamilyMemberModel,
                    (FamilyMemberModel.group_id == FamilyGroupModel.id)
                    & (FamilyMemberModel.user_id == FamilyRegimenAssignmentModel.recipient_user_id),
                )
                .join(
                    IntakeEventModel,
                    IntakeEventModel.regimen_id == FamilyRegimenAssignmentModel.regimen_id,
                )
                .where(
                    FamilyGroupModel.owner_user_id == owner.id,
                    IntakeEventModel.scheduled_at >= now - timedelta(days=1),
                    IntakeEventModel.scheduled_at < now + timedelta(days=1),
                )
                .order_by(FamilyMemberModel.display_name, IntakeEventModel.scheduled_at)
            )
        ).all()
        result: list[FamilyIntakeStatus] = []
        for group, member, event in rows:
            zone = ZoneInfo(event.timezone)
            if event.scheduled_at.astimezone(zone).date() != now.astimezone(zone).date():
                continue
            result.append(
                FamilyIntakeStatus(
                    member.display_name,
                    group.name,
                    event.medication_name,
                    event.dose_amount,
                    event.dose_unit,
                    event.scheduled_at,
                    event.timezone,
                    event.status,
                    event.resolved_at,
                )
            )
        return result

    async def list_owned_assignments(self, owner_telegram_id: int) -> list[FamilyAssignmentSummary]:
        owner = await self._get_or_create_user(owner_telegram_id)
        rows = (
            await self._session.execute(
                select(
                    FamilyRegimenAssignmentModel.regimen_id,
                    FamilyGroupModel.name,
                    FamilyMemberModel.display_name,
                    RegimenModel.medication_name,
                    RegimenModel.medication_form,
                    RegimenModel.status,
                )
                .join(
                    FamilyGroupModel,
                    FamilyGroupModel.id == FamilyRegimenAssignmentModel.group_id,
                )
                .join(
                    FamilyMemberModel,
                    (FamilyMemberModel.group_id == FamilyGroupModel.id)
                    & (FamilyMemberModel.user_id == FamilyRegimenAssignmentModel.recipient_user_id),
                )
                .join(RegimenModel, RegimenModel.id == FamilyRegimenAssignmentModel.regimen_id)
                .where(FamilyGroupModel.owner_user_id == owner.id)
                .order_by(FamilyRegimenAssignmentModel.created_at.desc())
            )
        ).all()
        return [
            FamilyAssignmentSummary(
                regimen_id,
                group_name,
                display_name,
                medication_name,
                MedicationForm(medication_form),
                regimen_status,
            )
            for (
                regimen_id,
                group_name,
                display_name,
                medication_name,
                medication_form,
                regimen_status,
            ) in rows
        ]

    async def management_user_id(
        self, actor_telegram_id: int, regimen_id: UUID
    ) -> tuple[UUID, bool]:
        actor = await self._get_or_create_user(actor_telegram_id)
        row = (
            await self._session.execute(
                select(
                    FamilyRegimenAssignmentModel.recipient_user_id,
                    FamilyGroupModel.owner_user_id,
                )
                .join(
                    FamilyGroupModel,
                    FamilyGroupModel.id == FamilyRegimenAssignmentModel.group_id,
                )
                .where(FamilyRegimenAssignmentModel.regimen_id == regimen_id)
            )
        ).one_or_none()
        if row is None:
            return actor.id, False
        recipient_user_id, owner_user_id = row
        if owner_user_id != actor.id:
            raise FamilyAccessError("Семейное назначение может изменять только владелец группы")
        return recipient_user_id, True

    async def _owned_group(self, owner_id: UUID, group_id: UUID) -> FamilyGroupModel:
        group = (
            await self._session.scalars(
                select(FamilyGroupModel)
                .where(
                    FamilyGroupModel.id == group_id,
                    FamilyGroupModel.owner_user_id == owner_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if group is None:
            raise FamilyAccessError("Группа не найдена")
        return group

    async def _owned_member(
        self, owner_id: UUID, member_id: UUID
    ) -> tuple[FamilyMemberModel, UserModel]:
        row = (
            await self._session.execute(
                select(FamilyMemberModel, UserModel)
                .join(FamilyGroupModel, FamilyGroupModel.id == FamilyMemberModel.group_id)
                .join(UserModel, UserModel.id == FamilyMemberModel.user_id)
                .where(
                    FamilyMemberModel.id == member_id,
                    FamilyGroupModel.owner_user_id == owner_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            raise FamilyAccessError("Участник не найден")
        return row

    async def _remove_assignments(
        self, *conditions: ColumnElement[bool]
    ) -> dict[UUID, tuple[int, ...]]:
        assignment_rows = (
            await self._session.execute(
                select(
                    FamilyRegimenAssignmentModel.regimen_id,
                    FamilyRegimenAssignmentModel.recipient_user_id,
                ).where(*conditions)
            )
        ).all()
        if not assignment_rows:
            return {}
        regimen_ids = tuple(row.regimen_id for row in assignment_rows)
        recipient_ids = tuple({row.recipient_user_id for row in assignment_rows})
        message_rows = (
            await self._session.execute(
                select(RegimenModel.user_id, ReminderAttemptModel.telegram_message_id)
                .join(IntakeEventModel, IntakeEventModel.regimen_id == RegimenModel.id)
                .join(ReminderAttemptModel, ReminderAttemptModel.event_id == IntakeEventModel.id)
                .where(
                    RegimenModel.user_id.in_(recipient_ids),
                    RegimenModel.id.in_(regimen_ids),
                    ReminderAttemptModel.telegram_message_id.is_not(None),
                )
            )
        ).all()
        messages: dict[UUID, list[int]] = {}
        for user_id, message_id in message_rows:
            if message_id is not None:
                messages.setdefault(user_id, []).append(message_id)
        await self._session.execute(delete(RegimenModel).where(RegimenModel.id.in_(regimen_ids)))
        return {
            user_id: tuple(sorted(set(message_ids))) for user_id, message_ids in messages.items()
        }


def _clean_name(value: str, label: str) -> str:
    result = " ".join(value.split())
    if not 1 <= len(result) <= 64:
        raise FamilyAccessError(f"{label} должно содержать от 1 до 64 символов")
    return result


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
