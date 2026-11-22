"""Record daily bot and Mini App activity without message contents."""

import sqlalchemy as sa
from alembic import op

revision = "20261103_13_user_activity"
down_revision = "20261023_12_event_meal_timing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_activity",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("activity_date", sa.Date(), primary_key=True),
        sa.Column("channel", sa.String(16), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_activity_date", "user_activity", ["activity_date"])


def downgrade() -> None:
    op.drop_table("user_activity")
