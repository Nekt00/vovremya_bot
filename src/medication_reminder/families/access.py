from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.families.models import FamilyRegimenAssignmentModel
from medication_reminder.families.service import FamilyAccessError


async def ensure_recipient_cannot_manage_family_assignment(
    session: AsyncSession,
    *,
    regimen_id: UUID,
    user_id: UUID,
) -> None:
    delegated = (
        await session.scalars(
            select(FamilyRegimenAssignmentModel.regimen_id).where(
                FamilyRegimenAssignmentModel.regimen_id == regimen_id,
                FamilyRegimenAssignmentModel.recipient_user_id == user_id,
            )
        )
    ).one_or_none()
    if delegated is not None:
        raise FamilyAccessError("Семейное назначение может изменять только владелец группы")
