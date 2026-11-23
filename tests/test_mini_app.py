import hashlib
import hmac
import json
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlencode
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.application.windows import (
    current_window_intakes,
    next_today_intake,
)
from medication_reminder.intake_events.domain.event import IntakeEvent, IntakeEventStatus
from medication_reminder.main import create_app
from medication_reminder.medication_sets.domain import MedicationSet, MedicationSetDetails
from medication_reminder.mini_app_local import create_local_mini_app
from medication_reminder.presentation.http.mini_app import (
    EventActionRequest,
    RegimenCreateRequest,
    RegimenEditRequest,
    _create_report_download_token,
    _edited_schedule_rule,
    _event_action_values,
    _event_response,
    _is_direct_local_request,
    _new_regimen_command,
    _parse_report_download_token,
    _regimen_edit_data,
    _regimen_response,
    _signed_local_init_data,
    _summary,
    _today_set_responses,
    validate_telegram_init_data,
)
from medication_reminder.regimens.application.revisions import RevisionContext
from medication_reminder.regimens.domain.regimen import (
    MedicationForm,
    Regimen,
    RegimenStatus,
)
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    WeekdayScheduleRule,
)
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.shared.config import Settings


@pytest.mark.asyncio
@pytest.mark.parametrize("grouped", [False, True])
async def test_mini_app_updates_bot_screen_only_after_intake_is_committed(
    monkeypatch: pytest.MonkeyPatch, grouped: bool
) -> None:
    from medication_reminder.presentation.http import mini_app

    operations: list[str] = []
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock()
    transaction.__aexit__ = AsyncMock(side_effect=lambda *args: operations.append("commit"))
    session.begin.return_value = transaction
    session.__aexit__ = AsyncMock()
    app = create_app(Settings(environment="test"))
    app.state.session_factory = MagicMock(return_value=session)
    request = Request({"type": "http", "app": app})
    monkeypatch.setattr(mini_app, "_authenticated_telegram_user_id", lambda *args: 42)
    monkeypatch.setattr(
        mini_app,
        "GetOrCreateUser",
        lambda *args: AsyncMock(return_value=SimpleNamespace(id=uuid4(), timezone="UTC")),
    )

    async def refresh(*args: object) -> None:
        operations.append("refresh")

    monkeypatch.setattr(mini_app, "_refresh_bot_today", refresh)
    if grouped:
        monkeypatch.setattr(
            mini_app, "TakeMedicationSet", lambda *args, **kwargs: AsyncMock(return_value=2)
        )
        result = await mini_app.take_medication_set(
            uuid4(), mini_app.MedicationSetActionRequest(init_data="signed"), request
        )
        assert result.updated_count == 2
    else:
        monkeypatch.setattr(
            mini_app,
            "TransitionIntakeEvent",
            lambda *args: AsyncMock(
                return_value=SimpleNamespace(
                    id=uuid4(),
                    status=IntakeEventStatus.TAKEN,
                    snoozed_until=None,
                    taken_at=datetime.now(UTC),
                )
            ),
        )
        event_result = await mini_app.apply_event_action(
            uuid4(), EventActionRequest(init_data="signed", action="take"), request
        )
        assert event_result.status is IntakeEventStatus.TAKEN
    assert operations == ["commit", "refresh"]


def _signed_init_data(*, token: str, now: datetime, user_id: int = 42) -> str:
    values = {
        "auth_date": str(int(now.timestamp())),
        "query_id": "test-query",
        "user": json.dumps({"id": user_id}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_validates_signed_telegram_mini_app_identity() -> None:
    now = datetime(2026, 10, 17, 10, tzinfo=UTC)
    init_data = _signed_init_data(token="123:secret", now=now)

    assert validate_telegram_init_data(init_data, bot_token="123:secret", now=now) == 42


def test_rejects_tampered_telegram_mini_app_identity() -> None:
    now = datetime(2026, 10, 17, 10, tzinfo=UTC)
    init_data = _signed_init_data(token="123:secret", now=now).replace("test-query", "changed")

    with pytest.raises(HTTPException) as error:
        validate_telegram_init_data(init_data, bot_token="123:secret", now=now)

    assert error.value.status_code == 401


def test_local_session_uses_regular_telegram_signature() -> None:
    now = datetime(2026, 10, 20, 10, tzinfo=UTC)
    init_data = _signed_local_init_data(42, bot_token="123:secret", now=now)

    assert validate_telegram_init_data(init_data, bot_token="123:secret", now=now) == 42


def test_local_session_rejects_requests_forwarded_by_public_tunnel() -> None:
    direct = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/mini-app/local-session",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8001")],
            "client": ("127.0.0.1", 50_000),
            "server": ("127.0.0.1", 8001),
        }
    )
    forwarded = Request(
        {
            **direct.scope,
            "headers": [
                (b"host", b"127.0.0.1:8001"),
                (b"x-forwarded-for", b"203.0.113.10"),
            ],
        }
    )
    remote_with_localhost_host = Request(
        {
            **direct.scope,
            "headers": [(b"host", b"localhost:8001")],
            "client": ("192.0.2.10", 50_000),
        }
    )

    assert _is_direct_local_request(direct) is True
    assert _is_direct_local_request(forwarded) is False
    assert _is_direct_local_request(remote_with_localhost_host) is False
    assert _is_direct_local_request(remote_with_localhost_host, allow_docker_bridge=True) is True


@pytest.mark.asyncio
async def test_mini_app_uses_signed_http_endpoint_without_web_app_data_message() -> None:
    app = create_app(Settings(environment="test"))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/mini-app")

    assert response.status_code == 200
    assert "Telegram?.WebApp" in response.text
    assert "fetch('/mini-app/timezone'" in response.text
    assert "Новый курс" in response.text
    assert "Интервал повтора" in response.text
    assert "Отложить" in response.text
    assert "#0B6174" in response.text
    assert "--control-height: 44px" in response.text
    assert "--compact-action-width: 112px" in response.text
    assert "--focus-ring:" in response.text
    assert "minmax(104px, 1fr)" in response.text
    assert 'aria-current="page"' in response.text
    assert 'id="tab-indicator"' in response.text
    assert "background: var(--surface);" in response.text
    assert "background: linear-gradient(115deg, var(--tab-pill-start)" not in response.text
    assert "-webkit-tap-highlight-color: transparent" in response.text
    assert ".tab:focus:not(:focus-visible)" in response.text
    assert "function moveTabIndicator" in response.text
    assert "duration: 140" in response.text
    assert "bridgeLeft" not in response.text
    assert "Отметить приём вручную" in response.text
    assert 'id="history-planned-note"' in response.text
    assert "prefers-reduced-motion: reduce" in response.text
    assert "['Просрочен', formatted]" in response.text
    assert 'id="today-empty"' not in response.text
    assert 'id="family-actions"' in response.text
    assert "function showFormError" in response.text
    assert "heading?.focus({ preventScroll: true })" in response.text
    assert 'role="tab"' not in response.text
    assert "set-take-button" in response.text
    assert "font-synthesis" not in response.text
    assert "Принять всё" in response.text
    assert 'id="next-intake-action"' in response.text
    assert "next.textContent = medications.join(', ')" in response.text
    assert "more.className = 'regimen-more'" in response.text
    assert "@media (max-width: 440px)" in response.text
    assert 'id="regimen-jump-nav"' in response.text
    assert "Раннее время" in response.text
    assert 'id="icon-syringe"' in response.text
    assert 'href="#icon-calendar-check"' in response.text
    assert 'viewBox="0 0 24 24" fill="none" stroke="currentColor"' in response.text
    assert response.text.count('viewBox="0 0 256 256"') == 1
    assert "'/mini-app/settings'" in response.text
    assert "'/mini-app/sets/manage'" in response.text
    assert "'/mini-app/regimens/create'" in response.text
    assert "'/mini-app/family'" in response.text
    assert 'id="family-tab"' in response.text
    assert 'id="icon-users"' in response.text
    assert 'id="invite-family-button"' in response.text
    assert 'id="family-invite-group"' in response.text
    assert 'value="dependent"' in response.text
    assert 'value="self_managed"' in response.text
    assert "'/mini-app/family/invitations'" in response.text
    assert "'/mini-app/reports/preview'" in response.text
    assert "'/mini-app/reports/pdf-link'" in response.text
    assert 'id="open-report-button"' in response.text
    assert 'id="report-dialog"' in response.text
    assert "/mini-app/family/groups/${encodeURIComponent(group.id)}/rename" in response.text
    assert "/mini-app/family/members/${encodeURIComponent(member.id)}/delete" in response.text
    assert "'/mini-app/local-session'" in response.text
    assert "sendData" not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_local_tunnel_app_exposes_only_mini_app_routes() -> None:
    app = create_local_mini_app(Settings(environment="test"))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        mini_app = await client.get("/mini-app")
        docs = await client.get("/docs")
        health = await client.get("/health")
        ready = await client.get("/ready")
        dashboard = await client.post("/mini-app/dashboard")
        settings = await client.post("/mini-app/settings")
        action = await client.post(f"/mini-app/events/{uuid4()}/action")
        regimens = await client.post("/mini-app/regimens")
        family = await client.post("/mini-app/family")
        family_invite = await client.post("/mini-app/family/invitations")
        family_group_rename = await client.post(f"/mini-app/family/groups/{uuid4()}/rename")
        family_group_delete = await client.post(f"/mini-app/family/groups/{uuid4()}/delete")
        family_member_rename = await client.post(f"/mini-app/family/members/{uuid4()}/rename")
        family_member_delete = await client.post(f"/mini-app/family/members/{uuid4()}/delete")
        create_regimen = await client.post("/mini-app/regimens/create")
        regimen_action = await client.post(f"/mini-app/regimens/{uuid4()}/action")
        delete_regimen = await client.post(f"/mini-app/regimens/{uuid4()}/delete")
        edit_data = await client.post(f"/mini-app/regimens/{uuid4()}/edit-data")
        edit_regimen = await client.post(f"/mini-app/regimens/{uuid4()}/edit")
        manage_sets = await client.post("/mini-app/sets/manage")
        create_set = await client.post("/mini-app/sets/create")
        update_set = await client.post(f"/mini-app/sets/{uuid4()}/members")
        delete_set = await client.post(f"/mini-app/sets/{uuid4()}/delete")
        set_action = await client.post(f"/mini-app/sets/{uuid4()}/take")
        report_preview = await client.post("/mini-app/reports/preview")
        report_pdf = await client.post("/mini-app/reports/pdf")
        report_pdf_link = await client.post("/mini-app/reports/pdf-link")

    assert mini_app.status_code == 200
    assert mini_app.headers["content-encoding"] == "gzip"
    assert docs.status_code == 404
    assert health.status_code == 404
    assert ready.status_code == 404
    assert dashboard.status_code == 422
    assert settings.status_code == 422
    assert action.status_code == 422
    assert regimens.status_code == 422
    assert family.status_code == 422
    assert family_invite.status_code == 422
    assert family_group_rename.status_code == 422
    assert family_group_delete.status_code == 422
    assert family_member_rename.status_code == 422
    assert family_member_delete.status_code == 422
    assert create_regimen.status_code == 422
    assert regimen_action.status_code == 422
    assert delete_regimen.status_code == 422
    assert edit_data.status_code == 422
    assert edit_regimen.status_code == 422
    assert manage_sets.status_code == 422
    assert create_set.status_code == 422
    assert update_set.status_code == 422
    assert delete_set.status_code == 422
    assert set_action.status_code == 422
    assert report_preview.status_code == 422
    assert report_pdf.status_code == 422
    assert report_pdf_link.status_code == 422


def test_report_download_token_is_short_lived_and_tamper_proof() -> None:
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    regimen_id = uuid4()
    token = _create_report_download_token(
        telegram_user_id=42,
        period="30",
        regimen_id=regimen_id,
        bot_token="123:secret",
        now=now,
    )

    assert _parse_report_download_token(
        token,
        bot_token="123:secret",
        now=now,
    ) == (42, "30", regimen_id)
    with pytest.raises(ValueError, match="expired"):
        _parse_report_download_token(
            token,
            bot_token="123:secret",
            now=now.replace(minute=6),
        )
    with pytest.raises(ValueError, match="signature"):
        _parse_report_download_token(
            f"{token}0",
            bot_token="123:secret",
            now=now,
        )


def test_snooze_action_calculates_requested_delay() -> None:
    now = datetime(2026, 10, 21, 9, tzinfo=UTC)

    status_value, snoozed_until = _event_action_values(
        EventActionRequest(init_data="signed", action="snooze", minutes=30),
        now=now,
    )

    assert status_value is IntakeEventStatus.SNOOZED
    assert snoozed_until == datetime(2026, 10, 21, 9, 30, tzinfo=UTC)


def test_snooze_action_requires_delay() -> None:
    with pytest.raises(ValueError, match="Выберите время отсрочки"):
        _event_action_values(
            EventActionRequest(init_data="signed", action="snooze"),
            now=datetime(2026, 10, 21, 9, tzinfo=UTC),
        )


def test_undo_action_returns_to_pending_without_a_snooze() -> None:
    target, delay = _event_action_values(
        EventActionRequest(init_data="signed", action="undo"), now=datetime.now(UTC)
    )
    assert target is IntakeEventStatus.SCHEDULED
    assert delay is None


def test_create_request_reuses_wizard_validation_for_exact_schedule() -> None:
    command = _new_regimen_command(
        RegimenCreateRequest(
            init_data="signed",
            medication_name="Витамин D3",
            medication_form="tablet",
            dose_amount="2",
            dose_unit="таблетки",
            start_date=date(2026, 10, 20),
            reminder_target="exact",
            schedule_kind="daily",
            times=["08:00", "21:00"],
            ending_kind="total_intakes",
            total_intakes=30,
        )
    )

    assert isinstance(command.rule, DailyScheduleRule)
    assert command.rule.times == (time(8), time(21))
    assert command.total_intakes == 30
    assert command.medication_set is None


def test_create_request_maps_morning_target_to_medication_set() -> None:
    command = _new_regimen_command(
        RegimenCreateRequest(
            init_data="signed",
            medication_name="Магний",
            medication_form="capsule",
            dose_amount="1",
            dose_unit="капсула",
            start_date=date(2026, 10, 20),
            reminder_target="morning",
            schedule_kind="interval",
            every_days=3,
            ending_kind="open_ended",
        )
    )

    assert isinstance(command.rule, IntervalScheduleRule)
    assert command.rule.every_days == 3
    assert command.rule.times == (time(6),)
    assert command.medication_set is not None
    assert command.medication_set.name == "Утро"


def test_edit_request_builds_exact_weekday_schedule() -> None:
    rule = _edited_schedule_rule(
        RegimenEditRequest(
            init_data="signed",
            dose_amount="2,5",
            reminder_target="exact",
            schedule_kind="weekdays",
            weekdays=[1, 3, 5],
            times=["07:30", "21:00"],
        ),
        None,
    )

    assert isinstance(rule, WeekdayScheduleRule)
    assert rule.weekdays == frozenset({1, 3, 5})
    assert rule.times == (time(7, 30), time(21))


def _event_details(
    status: IntakeEventStatus,
    *,
    regimen_id: UUID | None = None,
) -> IntakeEventDetails:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    event = IntakeEvent(
        id=uuid4(),
        regimen_id=regimen_id or uuid4(),
        schedule_rule_id=uuid4(),
        sequence_number=1,
        scheduled_at=now,
        timezone="Europe/Moscow",
        status=status,
        snoozed_until=None,
        resolved_at=now if status.is_terminal else None,
        created_at=now,
        updated_at=now,
    )
    return IntakeEventDetails(
        event=event,
        medication_name="Витамин D3",
        medication_form=MedicationForm.TABLET,
        dose_amount=Decimal("2.00"),
        dose_unit="таблетки",
    )


def test_dashboard_event_response_is_frontend_ready() -> None:
    response = _event_response(_event_details(IntakeEventStatus.DUE))

    assert response.medication_name == "Витамин D3"
    assert response.medication_form == "tablet"
    assert response.dose_amount == "2"
    assert response.status is IntakeEventStatus.DUE
    assert response.taken_at is None


def test_dashboard_event_response_exposes_actual_taken_time() -> None:
    details = _event_details(IntakeEventStatus.TAKEN)

    response = _event_response(details)

    assert response.taken_at == details.event.resolved_at


def test_dashboard_summary_counts_adherence() -> None:
    summary = _summary(
        [
            _event_details(IntakeEventStatus.TAKEN),
            _event_details(IntakeEventStatus.SKIPPED),
            _event_details(IntakeEventStatus.SCHEDULED),
        ]
    )

    assert summary.taken == 1
    assert summary.skipped == 1
    assert summary.pending == 1
    assert summary.adherence_percent == 50


def test_dashboard_groups_today_events_by_medication_set() -> None:
    now = datetime(2026, 10, 20, 8, tzinfo=UTC)
    user_id = uuid4()
    regimen = Regimen(
        id=uuid4(),
        user_id=user_id,
        medication_name="Витамин D3",
        medication_form=MedicationForm.TABLET,
        dose_amount=Decimal("2"),
        dose_unit="таблетки",
        start_date=date(2026, 10, 20),
        total_intakes=None,
        end_date=None,
        status=RegimenStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    medication_set = MedicationSet(
        id=uuid4(),
        user_id=user_id,
        name="Утро",
        window_start=time(6),
        window_end=time(12),
        timezone="Europe/Moscow",
        active=True,
        created_at=now,
        updated_at=now,
    )
    event = _event_details(IntakeEventStatus.SCHEDULED, regimen_id=regimen.id)
    event = replace(event, event=replace(event.event, scheduled_at=now.replace(hour=6)))
    outside = replace(
        event, event=replace(event.event, id=uuid4(), scheduled_at=now.replace(hour=18))
    )

    result = _today_set_responses(
        [MedicationSetDetails(medication_set, (regimen,))],
        [event, outside],
    )

    assert len(result) == 1
    assert result[0].name == "Утро"
    assert result[0].window_start == "06:00"
    assert result[0].event_ids == [event.event.id]

    evening_regimen = replace(regimen, id=uuid4())
    evening_set = replace(
        medication_set, id=uuid4(), name="Вечер", window_start=time(18), window_end=time(23)
    )
    evening = replace(outside, event=replace(outside.event, regimen_id=evening_regimen.id))
    sets = [
        MedicationSetDetails(medication_set, (regimen,)),
        MedicationSetDetails(evening_set, (evening_regimen,)),
    ]
    events = [event, outside, evening]
    morning = current_window_intakes(events, sets, now=now)
    assert [item.event.id for item in morning] == [event.event.id]
    # Moscow 12:00 is the exclusive end of the morning window.
    assert current_window_intakes(events, sets, now=now.replace(hour=9)) == []
    evening_events = current_window_intakes(events, sets, now=now.replace(hour=18))
    assert [item.event.id for item in evening_events] == [evening.event.id]
    assert current_window_intakes(events, sets, now=now.replace(hour=20)) == []
    upcoming = next_today_intake(events, sets, now=now)
    assert upcoming is not None
    assert upcoming.label == "Вечер"
    assert upcoming.at == evening.event.scheduled_at
    assert next_today_intake(events, sets, now=now.replace(hour=20)) is None
    snoozed = replace(
        event,
        event=replace(
            event.event, status=IntakeEventStatus.SNOOZED, snoozed_until=now + timedelta(minutes=15)
        ),
    )
    upcoming_snooze = next_today_intake([snoozed, evening], sets, now=now)
    assert upcoming_snooze is not None
    assert upcoming_snooze.at == snoozed.event.snoozed_until
    assert upcoming_snooze.label == "Утро"


def test_regimen_response_formats_course_and_interval_schedule() -> None:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    regimen = Regimen(
        id=uuid4(),
        user_id=uuid4(),
        medication_name="Препарат",
        medication_form=MedicationForm.INJECTION,
        dose_amount=Decimal("1.00"),
        dose_unit="мг",
        start_date=date(2026, 10, 17),
        total_intakes=35,
        end_date=None,
        status=RegimenStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    schedule = StoredScheduleRule(
        id=uuid4(),
        regimen_id=regimen.id,
        rule=IntervalScheduleRule(every_days=3, times=(time(6), time(18))),
        timezone="Europe/Moscow",
        version=1,
        active=True,
        created_at=now,
    )

    response = _regimen_response(regimen, schedule)

    assert response.medication_form == "injection"
    assert response.dose_amount == "1"
    assert response.ending == "35 приёмов"
    assert response.schedule == "Каждые 3 дн. в 06:00, 18:00"
    assert response.intake_periods == ["morning", "evening"]


def test_regimen_edit_data_reports_remaining_and_preserves_exact_times() -> None:
    now = datetime(2026, 10, 17, 8, tzinfo=UTC)
    regimen = Regimen(
        id=uuid4(),
        user_id=uuid4(),
        medication_name="Препарат",
        medication_form=MedicationForm.TABLET,
        dose_amount=Decimal("1.5"),
        dose_unit="таблетки",
        start_date=date(2026, 10, 17),
        total_intakes=20,
        end_date=None,
        status=RegimenStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    schedule = StoredScheduleRule(
        id=uuid4(),
        regimen_id=regimen.id,
        rule=DailyScheduleRule((time(8), time(21))),
        timezone="Europe/Moscow",
        version=1,
        active=True,
        created_at=now,
    )

    response = _regimen_edit_data(
        RevisionContext(
            regimen=regimen,
            active_schedule=schedule,
            replaceable_count=12,
            resolved_count=6,
            pending_count=2,
        ),
        None,
    )

    assert response.reminder_target == "exact"
    assert response.schedule_kind == "daily"
    assert response.times == ["08:00", "21:00"]
    assert response.remaining_intakes == 14
    assert response.minimum_remaining_intakes == 2
