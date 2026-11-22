from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.families.models import (
    FamilyGroupModel,
    FamilyInvitationModel,
    FamilyMemberModel,
    FamilyRegimenAssignmentModel,
)
from medication_reminder.families.service import FamilyAccessError, FamilyService
from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.regimens.infrastructure.models import RegimenModel
from medication_reminder.reminders.models import ReminderAttemptModel
from medication_reminder.schedules.infrastructure.models import ScheduleRuleModel
from medication_reminder.users.application.use_cases import GetOrCreateUser
from medication_reminder.users.infrastructure.models import UserModel
from medication_reminder.users.infrastructure.repository import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration


async def _add_user(session: AsyncSession, telegram_id: int) -> UUID:
    user_id = uuid4()
    session.add(
        UserModel(
            id=user_id,
            telegram_user_id=telegram_id,
            timezone="UTC",
            reminder_repeat_minutes=30,
            reminders_enabled=True,
        )
    )
    await session.flush()
    return user_id


async def _add_regimen(session: AsyncSession, user_id: UUID, name: str) -> tuple[UUID, UUID]:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    regimen_id = uuid4()
    schedule_id = uuid4()
    session.add(
        RegimenModel(
            id=regimen_id,
            user_id=user_id,
            medication_name=name,
            medication_form="tablet",
            dose_amount=Decimal("1"),
            dose_unit="таблетка",
            start_date=now.date(),
            total_intakes=10,
            end_date=None,
            status="active",
            meal_timing="independent",
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        ScheduleRuleModel(
            id=schedule_id,
            regimen_id=regimen_id,
            kind="daily",
            payload={"times": ["09:00"]},
            timezone="UTC",
            version=1,
            active=True,
            created_at=now,
        )
    )
    await session.flush()
    return regimen_id, schedule_id


@pytest.mark.asyncio
async def test_remove_member_deletes_only_delegated_regimens_and_returns_messages(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    owner_id = await _add_user(db_session, 7001)
    member_user_id = await _add_user(db_session, 7002)
    group_id = uuid4()
    member_id = uuid4()
    db_session.add(
        FamilyGroupModel(
            id=group_id,
            owner_user_id=owner_id,
            name="Семья",
            normalized_name="семья",
            created_at=now,
        )
    )
    db_session.add(
        FamilyMemberModel(
            id=member_id,
            group_id=group_id,
            user_id=member_user_id,
            display_name="Саша",
            joined_at=now,
        )
    )
    delegated_id, schedule_id = await _add_regimen(db_session, member_user_id, "Железо")
    personal_id, personal_schedule_id = await _add_regimen(db_session, member_user_id, "Магний")
    db_session.add(
        FamilyRegimenAssignmentModel(
            regimen_id=delegated_id,
            group_id=group_id,
            assigned_by_user_id=owner_id,
            recipient_user_id=member_user_id,
            created_at=now,
        )
    )
    event_id = uuid4()
    db_session.add(
        IntakeEventModel(
            id=event_id,
            regimen_id=delegated_id,
            schedule_rule_id=schedule_id,
            sequence_number=1,
            scheduled_at=now,
            timezone="UTC",
            medication_name="Железо",
            medication_form="tablet",
            dose_amount=Decimal("1"),
            dose_unit="таблетка",
            meal_timing="independent",
            status="due",
            snoozed_until=None,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        ReminderAttemptModel(
            id=uuid4(),
            event_id=event_id,
            idempotency_key=f"family:{event_id}",
            scheduled_for=now,
            status="sent",
            claim_token=uuid4(),
            claimed_at=now,
            sent_at=now,
            telegram_message_id=321,
            failure_reason=None,
            attempt_count=1,
            created_at=now,
            updated_at=now,
        )
    )
    personal_event_id = uuid4()
    db_session.add(
        IntakeEventModel(
            id=personal_event_id,
            regimen_id=personal_id,
            schedule_rule_id=personal_schedule_id,
            sequence_number=1,
            scheduled_at=now,
            timezone="UTC",
            medication_name="Магний",
            medication_form="tablet",
            dose_amount=Decimal("1"),
            dose_unit="таблетка",
            meal_timing="independent",
            status="due",
            snoozed_until=None,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        ReminderAttemptModel(
            id=uuid4(),
            event_id=personal_event_id,
            idempotency_key=f"personal:{personal_event_id}",
            scheduled_for=now,
            status="sent",
            claim_token=uuid4(),
            claimed_at=now,
            sent_at=now,
            telegram_message_id=654,
            failure_reason=None,
            attempt_count=1,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()

    service = FamilyService(
        db_session,
        GetOrCreateUser(SqlAlchemyUserRepository(db_session)),
        clock=lambda: now,
    )
    with pytest.raises(FamilyAccessError, match="Группа не найдена"):
        await service.rename_group(7002, group_id=group_id, name="Чужая группа")
    await service.rename_group(7001, group_id=group_id, name="Дети")
    await service.rename_member(7001, member_id=member_id, display_name="Александр")
    removed = await service.remove_member(7001, member_id=member_id)

    assert removed.chats[0].telegram_user_id == 7002
    assert removed.chats[0].message_ids == (321,)
    assert await db_session.get(RegimenModel, delegated_id) is None
    assert await db_session.get(RegimenModel, personal_id) is not None
    assert await db_session.get(FamilyMemberModel, member_id) is None
    group = await db_session.get(FamilyGroupModel, group_id)
    assert group is not None and group.name == "Дети"


@pytest.mark.asyncio
async def test_delete_group_removes_all_family_assignments(db_session: AsyncSession) -> None:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    owner_id = await _add_user(db_session, 7101)
    member_user_id = await _add_user(db_session, 7102)
    group_id = uuid4()
    db_session.add(
        FamilyGroupModel(
            id=group_id,
            owner_user_id=owner_id,
            name="Родители",
            normalized_name="родители",
            created_at=now,
        )
    )
    db_session.add(
        FamilyMemberModel(
            id=uuid4(),
            group_id=group_id,
            user_id=member_user_id,
            display_name="Мама",
            joined_at=now,
        )
    )
    regimen_id, _ = await _add_regimen(db_session, member_user_id, "D3")
    db_session.add(
        FamilyRegimenAssignmentModel(
            regimen_id=regimen_id,
            group_id=group_id,
            assigned_by_user_id=owner_id,
            recipient_user_id=member_user_id,
            created_at=now,
        )
    )
    await db_session.flush()

    service = FamilyService(
        db_session,
        GetOrCreateUser(SqlAlchemyUserRepository(db_session)),
        clock=lambda: now,
    )
    removed = await service.delete_group(7101, group_id=group_id)

    assert [chat.telegram_user_id for chat in removed.chats] == [7102]
    assert await db_session.get(FamilyGroupModel, group_id) is None
    assert await db_session.get(RegimenModel, regimen_id) is None


@pytest.mark.asyncio
async def test_owner_account_deletion_removes_delegated_regimens_only(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    owner_id = await _add_user(db_session, 7151)
    recipient_id = await _add_user(db_session, 7152)
    group_id = uuid4()
    db_session.add(
        FamilyGroupModel(
            id=group_id,
            owner_user_id=owner_id,
            name="Семья",
            normalized_name="семья",
            created_at=now,
        )
    )
    db_session.add(
        FamilyMemberModel(
            id=uuid4(),
            group_id=group_id,
            user_id=recipient_id,
            display_name="Саша",
            joined_at=now,
        )
    )
    delegated_id, _ = await _add_regimen(db_session, recipient_id, "Железо")
    personal_id, _ = await _add_regimen(db_session, recipient_id, "Магний")
    db_session.add(
        FamilyRegimenAssignmentModel(
            regimen_id=delegated_id,
            group_id=group_id,
            assigned_by_user_id=owner_id,
            recipient_user_id=recipient_id,
            created_at=now,
        )
    )
    await db_session.flush()

    repository = SqlAlchemyUserRepository(db_session)
    service = FamilyService(db_session, GetOrCreateUser(repository), clock=lambda: now)
    await service.remove_owned_assignments_for_account_deletion(7151)
    assert await repository.delete_user_data(7151) is True
    await db_session.flush()

    assert await db_session.get(UserModel, owner_id) is None
    assert await db_session.get(RegimenModel, delegated_id) is None
    assert await db_session.get(RegimenModel, personal_id) is not None


@pytest.mark.asyncio
async def test_invitation_uses_selected_group_and_restricts_dependent_role(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    owner_id = await _add_user(db_session, 7201)
    group_id = uuid4()
    db_session.add(
        FamilyGroupModel(
            id=group_id,
            owner_user_id=owner_id,
            name="Дети",
            normalized_name="дети",
            created_at=now,
        )
    )
    await db_session.flush()
    service = FamilyService(
        db_session,
        GetOrCreateUser(SqlAlchemyUserRepository(db_session)),
        clock=lambda: now,
    )

    invitation = await service.create_invitation(
        7201,
        group_id=group_id,
        display_name="Саша",
        role="dependent",
    )
    accepted = await service.accept_invitation(7202, invitation.token)

    member = (
        await db_session.scalars(
            select(FamilyMemberModel).where(
                FamilyMemberModel.group_id == group_id,
                FamilyMemberModel.display_name == "Саша",
            )
        )
    ).one()
    assert accepted.role == "dependent"
    assert member.role == "dependent"
    assert not await service.can_manage_personal_regimens(7202)
    assert await service.can_manage_personal_regimens(7201)
    assert await db_session.scalar(select(func.count()).select_from(FamilyMemberModel)) == 1
    with pytest.raises(FamilyAccessError, match="уже использовано"):
        await service.accept_invitation(7203, invitation.token)

    regimen_id, _ = await _add_regimen(db_session, member.user_id, "Омега-3")
    db_session.add(
        FamilyRegimenAssignmentModel(
            regimen_id=regimen_id,
            group_id=group_id,
            assigned_by_user_id=owner_id,
            recipient_user_id=member.user_id,
            created_at=now,
        )
    )
    await db_session.flush()
    assert await service.management_user_id(7201, regimen_id) == (member.user_id, True)
    with pytest.raises(FamilyAccessError, match="только владелец"):
        await service.management_user_id(7202, regimen_id)


@pytest.mark.asyncio
async def test_repeated_group_name_reuses_group(db_session: AsyncSession) -> None:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    await _add_user(db_session, 7301)
    service = FamilyService(
        db_session,
        GetOrCreateUser(SqlAlchemyUserRepository(db_session)),
        clock=lambda: now,
    )

    first = await service.create_invitation(7301, group_name="Семья", display_name="Мама")
    second = await service.create_invitation(7301, group_name="Семья", display_name="Папа")

    assert first.group_name == second.group_name == "Семья"
    assert await db_session.scalar(select(func.count()).select_from(FamilyGroupModel)) == 1
    assert await db_session.scalar(select(func.count()).select_from(FamilyInvitationModel)) == 2
