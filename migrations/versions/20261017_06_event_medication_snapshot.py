"""Store medication snapshot on intake events.

Revision ID: 20261017_06_event_snapshot
Revises: 20261017_05_abandoned_reminders
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_06_event_snapshot"
down_revision: str | None = "20261017_05_abandoned_reminders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("intake_events", sa.Column("medication_name", sa.String(120)))
    op.add_column("intake_events", sa.Column("medication_form", sa.String(16)))
    op.add_column("intake_events", sa.Column("dose_amount", sa.Numeric()))
    op.add_column("intake_events", sa.Column("dose_unit", sa.String(32)))
    op.execute(
        """
        UPDATE intake_events AS event
        SET medication_name = regimen.medication_name,
            medication_form = regimen.medication_form,
            dose_amount = regimen.dose_amount,
            dose_unit = regimen.dose_unit
        FROM regimens AS regimen
        WHERE regimen.id = event.regimen_id
        """
    )
    for column in ("medication_name", "medication_form", "dose_amount", "dose_unit"):
        op.alter_column("intake_events", column, nullable=False)
    op.create_check_constraint(
        "ck_intake_events_dose_amount_positive",
        "intake_events",
        "dose_amount > 0",
    )
    op.create_check_constraint(
        "ck_intake_events_medication_form",
        "intake_events",
        "medication_form IN ('tablet', 'capsule', 'injection', 'drops', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_intake_events_medication_form", "intake_events", type_="check")
    op.drop_constraint("ck_intake_events_dose_amount_positive", "intake_events", type_="check")
    op.drop_column("intake_events", "dose_unit")
    op.drop_column("intake_events", "dose_amount")
    op.drop_column("intake_events", "medication_form")
    op.drop_column("intake_events", "medication_name")
