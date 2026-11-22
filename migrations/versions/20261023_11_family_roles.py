"""Add family member roles.

Revision ID: 20261023_11_family_roles
Revises: 20261023_10_meal_timing
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_11_family_roles"
down_revision: str | None = "20261023_10_meal_timing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("family_members", "family_invitations"):
        op.add_column(
            table,
            sa.Column(
                "role",
                sa.String(length=24),
                server_default="self_managed",
                nullable=False,
            ),
        )
        op.create_check_constraint(
            f"ck_{table}_role",
            table,
            "role IN ('dependent', 'self_managed')",
        )


def downgrade() -> None:
    for table in ("family_invitations", "family_members"):
        op.drop_constraint(f"ck_{table}_role", table, type_="check")
        op.drop_column(table, "role")
