from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.families.observers import observers_for_events
from medication_reminder.reminders.models import ReminderAttemptModel
from medication_reminder.reminders.repository import _can_reclaim
from medication_reminder.reminders.worker import _should_restart_worker


class EmptyRows:
    def all(self) -> list[tuple[object, ...]]:
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statement: Any = None

    async def execute(self, statement: Any) -> EmptyRows:
        self.statement = statement
        return EmptyRows()


def make_attempt(*, status: str, at: datetime) -> ReminderAttemptModel:
    return ReminderAttemptModel(
        id=uuid4(),
        event_id=uuid4(),
        idempotency_key="key",
        scheduled_for=at,
        status=status,
        claim_token=uuid4(),
        claimed_at=at,
        sent_at=at if status == "sent" else None,
        failure_reason="failed" if status == "failed" else None,
        attempt_count=1,
        created_at=at,
        updated_at=at,
    )


def test_sent_attempt_is_never_reclaimed() -> None:
    now = datetime(2026, 10, 17, 10, tzinfo=UTC)
    assert not _can_reclaim(
        make_attempt(status="sent", at=now - timedelta(days=1)),
        now=now,
        retry_interval=timedelta(minutes=1),
        claim_timeout=timedelta(minutes=5),
    )


def test_abandoned_attempt_is_never_reclaimed() -> None:
    now = datetime(2026, 10, 17, 10, tzinfo=UTC)
    assert not _can_reclaim(
        make_attempt(status="abandoned", at=now - timedelta(days=30)),
        now=now,
        retry_interval=timedelta(minutes=1),
        claim_timeout=timedelta(minutes=5),
    )


def test_failed_and_stale_claims_are_reclaimed_only_after_timeout() -> None:
    now = datetime(2026, 10, 17, 10, tzinfo=UTC)
    retry = timedelta(minutes=1)
    timeout = timedelta(minutes=5)

    assert _can_reclaim(
        make_attempt(status="failed", at=now - retry),
        now=now,
        retry_interval=retry,
        claim_timeout=timeout,
    )
    assert _can_reclaim(
        make_attempt(status="claimed", at=now - timeout),
        now=now,
        retry_interval=retry,
        claim_timeout=timeout,
    )


def test_worker_restarts_after_consecutive_iteration_failures() -> None:
    assert not _should_restart_worker(5, 6)
    assert _should_restart_worker(6, 6)


@pytest.mark.asyncio
async def test_observer_lookup_locks_assignment_until_notification_finishes() -> None:
    session = CapturingSession()

    assert await observers_for_events(cast(AsyncSession, session), (uuid4(),)) == []

    dialect_factory: Any = postgresql.dialect
    sql = str(session.statement.compile(dialect=dialect_factory()))
    assert "FOR UPDATE OF family_regimen_assignments" in sql
