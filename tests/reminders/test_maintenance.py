from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import ClauseElement

from medication_reminder.reminders.maintenance import cleanup_terminal_reminder_attempts


class CapturingSession:
    def __init__(self) -> None:
        self.statement: Any = None

    async def scalars(self, statement: Any) -> list[object]:
        self.statement = statement
        return [uuid4(), uuid4()]


@pytest.mark.asyncio
async def test_cleanup_deletes_only_old_attempts_for_terminal_events() -> None:
    session = CapturingSession()
    before = datetime(2026, 7, 19, tzinfo=UTC)

    deleted = await cleanup_terminal_reminder_attempts(session, before=before)  # type: ignore[arg-type]

    assert deleted == 2
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    compiled = cast(ClauseElement, session.statement).compile(dialect=dialect)
    sql = str(compiled)
    assert sql.startswith("DELETE FROM reminder_attempts")
    assert "reminder_attempts.updated_at <" in sql
    assert "intake_events.status IN" in sql
    assert set(compiled.params["status_1"]) == {"taken", "skipped", "missed", "cancelled"}
