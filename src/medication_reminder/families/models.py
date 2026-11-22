from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from medication_reminder.shared.database import Base


class FamilyGroupModel(Base):
    __tablename__ = "family_groups"
    __table_args__ = (
        Index("uq_family_groups_owner_name", "owner_user_id", "normalized_name", unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FamilyMemberModel(Base):
    __tablename__ = "family_members"
    __table_args__ = (
        Index("uq_family_members_group_user", "group_id", "user_id", unique=True),
        Index("ix_family_members_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False, server_default="self_managed")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FamilyInvitationModel(Base):
    __tablename__ = "family_invitations"
    __table_args__ = (Index("uq_family_invitations_token_hash", "token_hash", unique=True),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False
    )
    invited_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False, server_default="self_managed")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FamilyRegimenAssignmentModel(Base):
    __tablename__ = "family_regimen_assignments"
    __table_args__ = (Index("ix_family_assignments_group_created", "group_id", "created_at"),)

    regimen_id: Mapped[UUID] = mapped_column(
        ForeignKey("regimens.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
