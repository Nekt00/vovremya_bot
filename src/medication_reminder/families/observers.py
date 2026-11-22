from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.families.models import (
    FamilyGroupModel,
    FamilyMemberModel,
    FamilyRegimenAssignmentModel,
)
from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.users.infrastructure.models import UserModel


@dataclass(frozen=True, slots=True)
class FamilyObserver:
    event_id: UUID
    owner_telegram_user_id: int
    group_name: str
    recipient_name: str


async def observers_for_events(
    session: AsyncSession, event_ids: tuple[UUID, ...]
) -> list[FamilyObserver]:
    if not event_ids:
        return []
    owner = UserModel.__table__.alias("family_owner")
    rows = (
        await session.execute(
            select(
                IntakeEventModel.id,
                owner.c.telegram_user_id,
                FamilyGroupModel.name,
                FamilyMemberModel.display_name,
            )
            .join(
                FamilyRegimenAssignmentModel,
                FamilyRegimenAssignmentModel.regimen_id == IntakeEventModel.regimen_id,
            )
            .join(FamilyGroupModel, FamilyGroupModel.id == FamilyRegimenAssignmentModel.group_id)
            .join(owner, owner.c.id == FamilyGroupModel.owner_user_id)
            .join(
                FamilyMemberModel,
                (FamilyMemberModel.group_id == FamilyGroupModel.id)
                & (FamilyMemberModel.user_id == FamilyRegimenAssignmentModel.recipient_user_id),
            )
            .where(IntakeEventModel.id.in_(event_ids))
            .with_for_update(of=FamilyRegimenAssignmentModel)
        )
    ).all()
    return [
        FamilyObserver(
            event_id=row[0],
            owner_telegram_user_id=row[1],
            group_name=row[2],
            recipient_name=row[3],
        )
        for row in rows
    ]
