from __future__ import annotations

import hashlib
import hmac
import json
import logging
from base64 import b64decode, urlsafe_b64encode
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal, cast
from urllib.parse import parse_qsl, urlencode
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medication_reminder.analytics.service import record_activity
from medication_reminder.families.access import (
    ensure_recipient_cannot_manage_family_assignment,
)
from medication_reminder.families.service import (
    FamilyAccessError,
    FamilyService,
    RemovedFamilyAccess,
)
from medication_reminder.intake_events.application.read_models import IntakeEventDetails
from medication_reminder.intake_events.application.use_cases import (
    IntakeEventNotFoundError,
    IntakeEventUpdateConflictError,
    ListUserIntakeEventDetails,
    TransitionIntakeEvent,
)
from medication_reminder.intake_events.application.windows import (
    current_window_intakes,
    next_today_intake,
)
from medication_reminder.intake_events.domain.event import (
    EventSource,
    IntakeEvent,
    IntakeEventStatus,
    InvalidIntakeTransitionError,
)
from medication_reminder.intake_events.infrastructure.repository import (
    SqlAlchemyIntakeEventRepository,
)
from medication_reminder.medication_sets.application import (
    AddRegimenToMedicationSet,
    CreateMedicationSet,
    CreateMedicationSetCommand,
    DeleteMedicationSet,
    ListMedicationSets,
    MedicationSetError,
    TakeMedicationSet,
    UpdateMedicationSet,
    UpdateMedicationSetCommand,
)
from medication_reminder.medication_sets.domain import MedicationSetDetails
from medication_reminder.medication_sets.presets import MEDICATION_SET_PRESETS
from medication_reminder.medication_sets.repository import SqlAlchemyMedicationSetRepository
from medication_reminder.presentation.http.mini_app_ui import MINI_APP_HTML
from medication_reminder.regimens.application.repositories import RegimenDeletionRepository
from medication_reminder.regimens.application.revisions import (
    NoFutureEventsError,
    RegimenRevisionConflictError,
    RegimenRevisionError,
    RegimenRevisionNotFoundError,
    RemainingIntakesTooSmallError,
    ReviseRegimen,
    ReviseRegimenCommand,
    RevisionContext,
)
from medication_reminder.regimens.application.use_cases import (
    ChangeRegimenStatus,
    CreateRegimen,
    ListUserRegimens,
    RegimenNotFoundError,
    RegimenUpdateConflictError,
)
from medication_reminder.regimens.domain.regimen import (
    InvalidStatusTransitionError,
    MealTiming,
    Regimen,
    RegimenStatus,
)
from medication_reminder.regimens.infrastructure.repository import SqlAlchemyRegimenRepository
from medication_reminder.regimens.infrastructure.revision_store import (
    SqlAlchemyRegimenRevisionStore,
)
from medication_reminder.reporting import (
    MedicationReport,
    ReportPeriod,
    build_medication_report,
    render_medication_report_pdf,
)
from medication_reminder.schedules.application.use_cases import MaterializeSchedule
from medication_reminder.schedules.domain.rules import (
    DailyScheduleRule,
    IntervalScheduleRule,
    ScheduleRule,
    WeekdayScheduleRule,
    WeeklyScheduleRule,
)
from medication_reminder.schedules.domain.schedule import StoredScheduleRule
from medication_reminder.schedules.infrastructure.repository import (
    SqlAlchemyScheduleMaterializationStore,
)
from medication_reminder.shared.config import Settings
from medication_reminder.shared.timezones import InvalidTimezoneError, validate_timezone
from medication_reminder.telegram.clean_chat import (
    SingleScreenRequestMiddleware,
    delete_family_reminder_messages,
)
from medication_reminder.telegram.clock import utc_now
from medication_reminder.telegram.service import TelegramApplicationService, TimezoneRequiredError
from medication_reminder.telegram.wizard_models import (
    EndingKind,
    NewRegimenCommand,
    ScheduleKind,
    WizardValidationError,
    build_rule,
    command_from_state,
    parse_dose_amount,
    parse_times,
)
from medication_reminder.telegram.wizard_service import (
    StaleStartDateError,
    WizardApplicationService,
)
from medication_reminder.users.application.use_cases import (
    GetOrCreateUser,
    UpdateReminderPreferences,
    UpdateUserTimezone,
)
from medication_reminder.users.infrastructure.models import UserModel
from medication_reminder.users.infrastructure.repository import SqlAlchemyUserRepository

router = APIRouter(prefix="/mini-app", tags=["mini-app"])
logger = logging.getLogger(__name__)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def mini_app_page() -> HTMLResponse:
    return HTMLResponse(
        MINI_APP_HTML,
        headers={
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org; "
                "style-src 'unsafe-inline'; connect-src 'self'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        },
    )


class TimezoneRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    timezone: str = Field(min_length=1, max_length=64)


class TimezoneResponse(BaseModel):
    timezone: str


class LocalSessionResponse(BaseModel):
    init_data: str


class ReminderSettingsResponse(BaseModel):
    repeat_minutes: Literal[15, 30, 60]
    reminders_enabled: bool


class ReminderSettingsUpdateRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    repeat_minutes: Literal[15, 30, 60]
    reminders_enabled: bool


class DashboardRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    history_days: Literal[7, 30] = 7


class ReportRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    period: ReportPeriod = "30"
    regimen_id: UUID | None = None


class ReportDownloadLinkResponse(BaseModel):
    url: str
    file_name: str = "vovremya-report.pdf"


class EventActionRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    action: Literal["take", "skip", "snooze", "undo"]
    minutes: Literal[15, 30, 60] | None = None


class RegimenListRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)


class FamilyDashboardRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)


class RegimenActionRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    action: Literal["pause", "resume", "complete"]


class MedicationSetActionRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)


class MedicationSetManagementRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)


class MedicationSetCreateRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    preset: Literal["morning", "day", "evening"]
    regimen_ids: list[UUID] = Field(min_length=1, max_length=100)


class MedicationSetUpdateRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    regimen_ids: list[UUID] = Field(min_length=1, max_length=100)


class RegimenCreateRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    medication_name: str = Field(min_length=1, max_length=120)
    medication_form: Literal["tablet", "capsule", "injection", "drops", "other"]
    dose_amount: str = Field(min_length=1, max_length=32)
    dose_unit: str = Field(min_length=1, max_length=32)
    meal_timing: Literal["independent", "before", "during", "after"] = "independent"
    start_date: date
    reminder_target: Literal["morning", "day", "evening", "exact"]
    schedule_kind: Literal["daily", "interval", "weekdays"]
    every_days: int | None = Field(default=None, ge=1, le=365)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    times: list[str] = Field(default_factory=list, max_length=24)
    ending_kind: Literal["total_intakes", "end_date", "open_ended"]
    total_intakes: int | None = Field(default=None, ge=1, le=10_000)
    end_date: date | None = None


class RegimenEditRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    dose_amount: str = Field(min_length=1, max_length=32)
    meal_timing: Literal["independent", "before", "during", "after"] | None = None
    reminder_target: Literal["morning", "day", "evening", "exact", "keep"]
    schedule_kind: Literal["daily", "interval", "weekdays"]
    every_days: int | None = Field(default=None, ge=1, le=365)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    times: list[str] = Field(default_factory=list, max_length=24)
    ending_kind: Literal["unchanged", "total_intakes", "end_date"] = "unchanged"
    remaining_intakes: int | None = Field(default=None, ge=1, le=10_000)
    end_date: date | None = None


class MiniAppEventResponse(BaseModel):
    id: UUID
    medication_name: str
    medication_form: str
    dose_amount: str
    dose_unit: str
    meal_timing: MealTiming
    scheduled_at: datetime
    taken_at: datetime | None
    snoozed_until: datetime | None
    status: IntakeEventStatus


class DashboardSummaryResponse(BaseModel):
    taken: int
    skipped: int
    pending: int
    adherence_percent: int | None


class MiniAppMedicationSetResponse(BaseModel):
    id: UUID
    name: str
    window_start: str
    window_end: str
    event_ids: list[UUID]


class MiniAppManagedSetResponse(BaseModel):
    id: UUID
    name: str
    window_start: str
    window_end: str
    regimen_ids: list[UUID]


class MiniAppSetRegimenResponse(BaseModel):
    id: UUID
    medication_name: str
    medication_form: str
    dose_amount: str
    dose_unit: str
    status: RegimenStatus
    assigned_set_id: UUID | None


class MedicationSetManagementResponse(BaseModel):
    sets: list[MiniAppManagedSetResponse]
    regimens: list[MiniAppSetRegimenResponse]


class UpcomingIntakeResponse(BaseModel):
    at: datetime
    label: str


class DashboardResponse(BaseModel):
    timezone: str | None
    can_manage_personal_regimens: bool
    settings: ReminderSettingsResponse
    today: list[MiniAppEventResponse]
    current_event_ids: list[UUID]
    next_intake: UpcomingIntakeResponse | None
    today_sets: list[MiniAppMedicationSetResponse]
    history: list[MiniAppEventResponse]
    summary: DashboardSummaryResponse


class ReportCourseResponse(BaseModel):
    id: UUID
    medication_name: str
    medication_form: str
    dose_amount: str
    dose_unit: str
    start_date: date
    status: str
    total_intakes: int | None
    taken: int
    missed: int
    pending: int
    remaining_to_target: int | None


class ReportEventResponse(BaseModel):
    scheduled_at: datetime
    resolved_at: datetime | None
    medication_name: str
    dose_amount: str
    dose_unit: str
    status: str


class MedicationReportResponse(BaseModel):
    timezone: str
    period: ReportPeriod
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    summary: DashboardSummaryResponse
    courses: list[ReportCourseResponse]
    events: list[ReportEventResponse]
    events_truncated: bool


class EventActionResponse(BaseModel):
    id: UUID
    status: IntakeEventStatus
    snoozed_until: datetime | None
    taken_at: datetime | None


class MedicationSetActionResponse(BaseModel):
    updated_count: int


class RegimenDeleteResponse(BaseModel):
    deleted: bool


class MedicationSetDeleteResponse(BaseModel):
    deleted: bool


class MiniAppRegimenResponse(BaseModel):
    id: UUID
    medication_name: str
    medication_form: str
    dose_amount: str
    dose_unit: str
    meal_timing: MealTiming
    start_date: date
    ending: str
    schedule: str
    intake_periods: list[Literal["early", "morning", "day", "evening"]]
    next_intake_at: datetime | None
    status: RegimenStatus


class RegimenListResponse(BaseModel):
    regimens: list[MiniAppRegimenResponse]


class RegimenCreateResponse(BaseModel):
    events_count: int


class RegimenEditDataResponse(BaseModel):
    id: UUID
    medication_name: str
    medication_form: str
    dose_amount: str
    dose_unit: str
    meal_timing: MealTiming
    start_date: date
    reminder_target: Literal["morning", "day", "evening", "exact", "keep"]
    reminder_label: str
    schedule_kind: Literal["daily", "interval", "weekdays"]
    every_days: int | None
    weekdays: list[int]
    times: list[str]
    ending: str
    remaining_intakes: int
    minimum_remaining_intakes: int
    end_date: date | None


class RegimenEditResponse(BaseModel):
    events_count: int


class FamilyMemberResponse(BaseModel):
    id: UUID
    display_name: str
    role: Literal["dependent", "self_managed"]


class FamilyGroupResponse(BaseModel):
    id: UUID
    name: str
    members: list[FamilyMemberResponse]


class FamilyStatusResponse(BaseModel):
    display_name: str
    group_name: str
    medication_name: str
    dose_amount: str
    dose_unit: str
    scheduled_at: datetime
    timezone: str
    status: str
    resolved_at: datetime | None


class FamilyAssignmentResponse(BaseModel):
    regimen_id: UUID
    group_name: str
    display_name: str
    medication_name: str
    medication_form: str
    status: str


class FamilyDashboardResponse(BaseModel):
    groups: list[FamilyGroupResponse]
    today: list[FamilyStatusResponse]
    assignments: list[FamilyAssignmentResponse]


class FamilyNameRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    name: str = Field(min_length=1, max_length=64)


class FamilyInvitationRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)
    group_id: UUID | None = None
    group_name: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    role: Literal["dependent", "self_managed"] = "self_managed"


class FamilyInvitationResponse(BaseModel):
    url: str
    expires_at: datetime


class FamilyMutationResponse(BaseModel):
    ok: bool = True


@router.get("/local-session", response_model=LocalSessionResponse)
async def local_session(request: Request) -> LocalSessionResponse:
    settings: Settings = request.app.state.settings
    if (
        not _is_direct_local_request(
            request, allow_docker_bridge=settings.local_session_allow_docker_bridge
        )
        or settings.environment != "local"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if settings.telegram_bot_token is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram bot is not configured")

    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        telegram_user_ids = list(
            (await session.scalars(select(UserModel.telegram_user_id).limit(2))).all()
        )
    if len(telegram_user_ids) != 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Локальный просмотр доступен, когда в базе ровно один пользователь",
        )
    return LocalSessionResponse(
        init_data=_signed_local_init_data(
            telegram_user_ids[0],
            bot_token=settings.telegram_bot_token.get_secret_value(),
        )
    )


@router.post("/timezone", response_model=TimezoneResponse)
async def update_timezone(payload: TimezoneRequest, request: Request) -> TimezoneResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    try:
        timezone = validate_timezone(payload.timezone)
    except InvalidTimezoneError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        repository = SqlAlchemyUserRepository(session)
        await GetOrCreateUser(repository)(telegram_user_id)
        user = await UpdateUserTimezone(repository)(telegram_user_id, timezone)
    return TimezoneResponse(timezone=user.timezone or timezone)


@router.post("/settings", response_model=ReminderSettingsResponse)
async def update_reminder_settings(
    payload: ReminderSettingsUpdateRequest,
    request: Request,
) -> ReminderSettingsResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        repository = SqlAlchemyUserRepository(session)
        await GetOrCreateUser(repository)(telegram_user_id)
        user = await UpdateReminderPreferences(repository)(
            telegram_user_id,
            repeat_minutes=payload.repeat_minutes,
            enabled=payload.reminders_enabled,
        )
    return ReminderSettingsResponse(
        repeat_minutes=cast(Literal[15, 30, 60], user.reminder_repeat_minutes),
        reminders_enabled=user.reminders_enabled,
    )


@router.post("/dashboard", response_model=DashboardResponse)
async def dashboard(payload: DashboardRequest, request: Request) -> DashboardResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        repository = SqlAlchemyUserRepository(session)
        user = await GetOrCreateUser(repository)(telegram_user_id)
        await record_activity(session, telegram_user_id, "mini_app", datetime.now(UTC))
        can_manage_personal = await FamilyService(
            session, GetOrCreateUser(repository)
        ).can_manage_personal_regimens(telegram_user_id)
        if user.timezone is None:
            return DashboardResponse(
                timezone=None,
                can_manage_personal_regimens=can_manage_personal,
                settings=ReminderSettingsResponse(
                    repeat_minutes=cast(Literal[15, 30, 60], user.reminder_repeat_minutes),
                    reminders_enabled=user.reminders_enabled,
                ),
                today=[],
                current_event_ids=[],
                next_intake=None,
                today_sets=[],
                history=[],
                summary=_summary([]),
            )

        now = datetime.now(UTC)
        zone = ZoneInfo(user.timezone)
        local_today = now.astimezone(zone).date()
        today_start = datetime.combine(local_today, time.min, zone).astimezone(UTC)
        today_end = datetime.combine(local_today + timedelta(days=1), time.min, zone).astimezone(
            UTC
        )
        history_start = datetime.combine(
            local_today - timedelta(days=payload.history_days - 1),
            time.min,
            zone,
        ).astimezone(UTC)

        list_details = ListUserIntakeEventDetails(SqlAlchemyIntakeEventRepository(session))
        today_details = await list_details(
            user.id,
            window_start=today_start,
            window_end=today_end,
        )
        history_details = await list_details(
            user.id,
            window_start=history_start,
            window_end=today_end,
        )
        medication_sets = await ListMedicationSets(SqlAlchemyMedicationSetRepository(session))(
            user.id
        )

    visible_today = [
        item for item in today_details if item.event.status is not IntakeEventStatus.CANCELLED
    ]
    visible_history = [
        item for item in history_details if item.event.status is not IntakeEventStatus.CANCELLED
    ]
    upcoming = next_today_intake(visible_today, medication_sets, now=now)
    return DashboardResponse(
        timezone=user.timezone,
        can_manage_personal_regimens=can_manage_personal,
        settings=ReminderSettingsResponse(
            repeat_minutes=cast(Literal[15, 30, 60], user.reminder_repeat_minutes),
            reminders_enabled=user.reminders_enabled,
        ),
        today=[_event_response(item) for item in visible_today],
        current_event_ids=[
            item.event.id
            for item in current_window_intakes(visible_today, medication_sets, now=now)
        ],
        next_intake=UpcomingIntakeResponse(at=upcoming.at, label=upcoming.label)
        if upcoming
        else None,
        today_sets=_today_set_responses(medication_sets, visible_today),
        history=[_event_response(item) for item in reversed(visible_history)],
        summary=_summary(visible_history),
    )


@router.post("/reports/preview", response_model=MedicationReportResponse)
async def preview_report(payload: ReportRequest, request: Request) -> MedicationReportResponse:
    report = await _build_authenticated_report(payload, request)
    return _report_response(report)


@router.post("/reports/pdf")
async def download_report(payload: ReportRequest, request: Request) -> Response:
    report = await _build_authenticated_report(payload, request)
    return Response(
        content=render_medication_report_pdf(report),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="vovremya-report.pdf"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/reports/pdf-link", response_model=ReportDownloadLinkResponse)
async def create_report_download_link(
    payload: ReportRequest,
    request: Request,
) -> ReportDownloadLinkResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    settings: Settings = request.app.state.settings
    if settings.telegram_bot_token is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram bot is not configured")
    token = _create_report_download_token(
        telegram_user_id=telegram_user_id,
        period=payload.period,
        regimen_id=payload.regimen_id,
        bot_token=settings.telegram_bot_token.get_secret_value(),
        now=utc_now(),
    )
    return ReportDownloadLinkResponse(url=f"/mini-app/reports/pdf/{token}")


@router.get("/reports/pdf/{token}")
async def download_report_from_link(token: str, request: Request) -> Response:
    settings: Settings = request.app.state.settings
    if settings.telegram_bot_token is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram bot is not configured")
    try:
        telegram_user_id, period, regimen_id = _parse_report_download_token(
            token,
            bot_token=settings.telegram_bot_token.get_secret_value(),
            now=utc_now(),
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка недействительна") from error
    report = await _build_report_for_user(
        request,
        telegram_user_id=telegram_user_id,
        period=period,
        regimen_id=regimen_id,
    )
    return Response(
        content=render_medication_report_pdf(report),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="vovremya-report.pdf"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/family", response_model=FamilyDashboardResponse)
async def family_dashboard(
    payload: FamilyDashboardRequest,
    request: Request,
) -> FamilyDashboardResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        repository = SqlAlchemyUserRepository(session)
        service = FamilyService(session, GetOrCreateUser(repository))
        groups = await service.list_owned_groups(telegram_user_id)
        statuses = await service.today_statuses(telegram_user_id)
        assignments = await service.list_owned_assignments(telegram_user_id)
    return FamilyDashboardResponse(
        groups=[
            FamilyGroupResponse(
                id=group.id,
                name=group.name,
                members=[
                    FamilyMemberResponse(
                        id=member.member_id,
                        display_name=member.display_name,
                        role=member.role,
                    )
                    for member in group.members
                ],
            )
            for group in groups
        ],
        today=[
            FamilyStatusResponse(
                display_name=item.display_name,
                group_name=item.group_name,
                medication_name=item.medication_name,
                dose_amount=_format_decimal(item.dose_amount),
                dose_unit=item.dose_unit,
                scheduled_at=item.scheduled_at,
                timezone=item.timezone,
                status=item.status,
                resolved_at=item.resolved_at,
            )
            for item in statuses
        ],
        assignments=[
            FamilyAssignmentResponse(
                regimen_id=item.regimen_id,
                group_name=item.group_name,
                display_name=item.display_name,
                medication_name=item.medication_name,
                medication_form=item.medication_form.value,
                status=item.status,
            )
            for item in assignments
        ],
    )


@router.post("/family/invitations", response_model=FamilyInvitationResponse)
async def create_family_invitation(
    payload: FamilyInvitationRequest,
    request: Request,
) -> FamilyInvitationResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    settings: Settings = request.app.state.settings
    if settings.telegram_bot_token is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram bot is not configured")
    bot = Bot(settings.telegram_bot_token.get_secret_value())
    try:
        username = (await bot.get_me()).username
    except TelegramAPIError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Не удалось подготовить ссылку приглашения",
        ) from error
    finally:
        await bot.session.close()
    if username is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "У бота не задано имя")

    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            service = FamilyService(
                session,
                GetOrCreateUser(SqlAlchemyUserRepository(session)),
            )
            invitation = await service.create_invitation(
                telegram_user_id,
                group_name=payload.group_name,
                group_id=payload.group_id,
                display_name=payload.display_name,
                role=payload.role,
            )
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return FamilyInvitationResponse(
        url=f"https://t.me/{username}?start=family_{invitation.token}",
        expires_at=invitation.expires_at,
    )


@router.post("/family/groups/{group_id}/rename", response_model=FamilyMutationResponse)
async def rename_family_group(
    group_id: UUID,
    payload: FamilyNameRequest,
    request: Request,
) -> FamilyMutationResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            await FamilyService(
                session,
                GetOrCreateUser(SqlAlchemyUserRepository(session)),
            ).rename_group(telegram_user_id, group_id=group_id, name=payload.name)
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return FamilyMutationResponse()


@router.post("/family/members/{member_id}/rename", response_model=FamilyMutationResponse)
async def rename_family_member(
    member_id: UUID,
    payload: FamilyNameRequest,
    request: Request,
) -> FamilyMutationResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            await FamilyService(
                session,
                GetOrCreateUser(SqlAlchemyUserRepository(session)),
            ).rename_member(
                telegram_user_id,
                member_id=member_id,
                display_name=payload.name,
            )
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return FamilyMutationResponse()


@router.post("/family/members/{member_id}/delete", response_model=FamilyMutationResponse)
async def delete_family_member(
    member_id: UUID,
    payload: FamilyDashboardRequest,
    request: Request,
) -> FamilyMutationResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            removed = await FamilyService(
                session,
                GetOrCreateUser(SqlAlchemyUserRepository(session)),
            ).remove_member(telegram_user_id, member_id=member_id)
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    await _clear_removed_family_messages(request, removed)
    return FamilyMutationResponse()


@router.post("/family/groups/{group_id}/delete", response_model=FamilyMutationResponse)
async def delete_family_group(
    group_id: UUID,
    payload: FamilyDashboardRequest,
    request: Request,
) -> FamilyMutationResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            removed = await FamilyService(
                session,
                GetOrCreateUser(SqlAlchemyUserRepository(session)),
            ).delete_group(telegram_user_id, group_id=group_id)
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    await _clear_removed_family_messages(request, removed)
    return FamilyMutationResponse()


@router.post("/events/{event_id}/action", response_model=EventActionResponse)
async def apply_event_action(
    event_id: UUID,
    payload: EventActionRequest,
    request: Request,
) -> EventActionResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    try:
        target_status, snoozed_until = _event_action_values(payload, now=utc_now())
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
            event = await TransitionIntakeEvent(SqlAlchemyIntakeEventRepository(session))(
                user.id,
                event_id,
                target_status,
                source=EventSource.USER,
                snoozed_until=snoozed_until,
            )
    except IntakeEventNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Приём не найден") from error
    except (InvalidIntakeTransitionError, IntakeEventUpdateConflictError) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    await _refresh_bot_today(request, telegram_user_id)
    return EventActionResponse(
        id=event.id,
        status=event.status,
        snoozed_until=event.snoozed_until,
        taken_at=event.taken_at,
    )


def _event_action_values(
    payload: EventActionRequest,
    *,
    now: datetime,
) -> tuple[IntakeEventStatus, datetime | None]:
    target_status = {
        "take": IntakeEventStatus.TAKEN,
        "skip": IntakeEventStatus.SKIPPED,
        "snooze": IntakeEventStatus.SNOOZED,
        "undo": IntakeEventStatus.SCHEDULED,
    }[payload.action]
    if payload.action != "snooze":
        return target_status, None
    if payload.minutes is None:
        raise ValueError("Выберите время отсрочки")
    return target_status, now + timedelta(minutes=payload.minutes)


@router.post("/sets/manage", response_model=MedicationSetManagementResponse)
async def manage_medication_sets(
    payload: MedicationSetManagementRequest,
    request: Request,
) -> MedicationSetManagementResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
        sets = await ListMedicationSets(SqlAlchemyMedicationSetRepository(session))(user.id)
        regimens = await ListUserRegimens(SqlAlchemyRegimenRepository(session))(user.id)
    assignments = {
        regimen.id: details.medication_set.id for details in sets for regimen in details.regimens
    }
    return MedicationSetManagementResponse(
        sets=[
            MiniAppManagedSetResponse(
                id=details.medication_set.id,
                name=details.medication_set.name,
                window_start=details.medication_set.window_start.strftime("%H:%M"),
                window_end=details.medication_set.window_end.strftime("%H:%M"),
                regimen_ids=[item.id for item in details.regimens],
            )
            for details in sets
        ],
        regimens=[
            MiniAppSetRegimenResponse(
                id=regimen.id,
                medication_name=regimen.medication_name,
                medication_form=regimen.medication_form.value,
                dose_amount=_format_decimal(regimen.dose_amount),
                dose_unit=regimen.dose_unit,
                status=regimen.status,
                assigned_set_id=assignments.get(regimen.id),
            )
            for regimen in regimens
        ],
    )


@router.post("/sets/create", response_model=MiniAppManagedSetResponse)
async def create_medication_set(
    payload: MedicationSetCreateRequest,
    request: Request,
) -> MiniAppManagedSetResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            await _ensure_personal_management(session, telegram_user_id)
            user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
            if user.timezone is None:
                raise TimezoneRequiredError("Сначала настройте часовой пояс")
            repository = SqlAlchemyMedicationSetRepository(session)
            name, window_start, window_end = MEDICATION_SET_PRESETS[payload.preset]
            existing = await ListMedicationSets(repository)(user.id)
            if any(item.medication_set.name.casefold() == name.casefold() for item in existing):
                raise MedicationSetError("Набор уже существует")
            medication_set = await CreateMedicationSet(repository, clock=utc_now)(
                CreateMedicationSetCommand(
                    user_id=user.id,
                    name=name,
                    window_start=window_start,
                    window_end=window_end,
                    timezone=user.timezone,
                    regimen_ids=tuple(payload.regimen_ids),
                )
            )
    except TimezoneRequiredError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except MedicationSetError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Не удалось создать набор") from error
    return MiniAppManagedSetResponse(
        id=medication_set.id,
        name=medication_set.name,
        window_start=medication_set.window_start.strftime("%H:%M"),
        window_end=medication_set.window_end.strftime("%H:%M"),
        regimen_ids=list(payload.regimen_ids),
    )


@router.post("/sets/{set_id}/members", response_model=MiniAppManagedSetResponse)
async def update_medication_set_members(
    set_id: UUID,
    payload: MedicationSetUpdateRequest,
    request: Request,
) -> MiniAppManagedSetResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            await _ensure_personal_management(session, telegram_user_id)
            user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
            repository = SqlAlchemyMedicationSetRepository(session)
            current = await repository.get_for_user(user.id, set_id)
            if current is None:
                raise MedicationSetError("Набор не найден")
            value = current.medication_set
            updated = await UpdateMedicationSet(repository, clock=utc_now)(
                UpdateMedicationSetCommand(
                    user_id=user.id,
                    set_id=set_id,
                    name=value.name,
                    window_start=value.window_start,
                    window_end=value.window_end,
                    regimen_ids=tuple(payload.regimen_ids),
                )
            )
    except MedicationSetError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Не удалось сохранить состав") from error
    return MiniAppManagedSetResponse(
        id=updated.medication_set.id,
        name=updated.medication_set.name,
        window_start=updated.medication_set.window_start.strftime("%H:%M"),
        window_end=updated.medication_set.window_end.strftime("%H:%M"),
        regimen_ids=[item.id for item in updated.regimens],
    )


@router.post("/sets/{set_id}/delete", response_model=MedicationSetDeleteResponse)
async def delete_medication_set(
    set_id: UUID,
    payload: MedicationSetManagementRequest,
    request: Request,
) -> MedicationSetDeleteResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            await _ensure_personal_management(session, telegram_user_id)
            user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
            await DeleteMedicationSet(SqlAlchemyMedicationSetRepository(session))(user.id, set_id)
    except MedicationSetError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Набор не найден") from error
    return MedicationSetDeleteResponse(deleted=True)


@router.post("/sets/{set_id}/take", response_model=MedicationSetActionResponse)
async def take_medication_set(
    set_id: UUID,
    payload: MedicationSetActionRequest,
    request: Request,
) -> MedicationSetActionResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
            if user.timezone is None:
                raise TimezoneRequiredError("Сначала настройте часовой пояс")
            local_date = utc_now().astimezone(ZoneInfo(user.timezone)).date()
            updated_count = await TakeMedicationSet(
                SqlAlchemyMedicationSetRepository(session),
                clock=utc_now,
            )(user.id, set_id, local_date)
    except TimezoneRequiredError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except MedicationSetError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "В наборе уже нет приёмов, ожидающих отметки",
        ) from error
    await _refresh_bot_today(request, telegram_user_id)
    return MedicationSetActionResponse(updated_count=updated_count)


@router.post("/regimens", response_model=RegimenListResponse)
async def list_regimens(payload: RegimenListRequest, request: Request) -> RegimenListResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
        repository = SqlAlchemyRegimenRepository(session)
        schedule_store = SqlAlchemyScheduleMaterializationStore(session)
        event_repository = SqlAlchemyIntakeEventRepository(session)
        regimens = await ListUserRegimens(repository)(user.id)
        responses = [
            _regimen_response(
                regimen,
                await schedule_store.get_active(regimen.id),
                (
                    await event_repository.next_pending_for_regimen(user.id, regimen.id)
                    if regimen.status is RegimenStatus.ACTIVE
                    else None
                ),
            )
            for regimen in regimens[:50]
        ]
    return RegimenListResponse(regimens=responses)


@router.post("/regimens/create", response_model=RegimenCreateResponse)
async def create_regimen(
    payload: RegimenCreateRequest,
    request: Request,
) -> RegimenCreateResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            user_repository = SqlAlchemyUserRepository(session)
            await FamilyService(
                session, GetOrCreateUser(user_repository)
            ).ensure_can_manage_personal_regimens(telegram_user_id)
            regimen_repository = SqlAlchemyRegimenRepository(session)
            schedule_store = SqlAlchemyScheduleMaterializationStore(session)
            set_repository = SqlAlchemyMedicationSetRepository(session)
            user = await GetOrCreateUser(user_repository)(telegram_user_id)
            existing_set_id: UUID | None = None
            if payload.reminder_target != "exact":
                preset_name = MEDICATION_SET_PRESETS[payload.reminder_target][0]
                existing_sets = await ListMedicationSets(set_repository)(user.id)
                existing_set = next(
                    (
                        item.medication_set
                        for item in existing_sets
                        if item.medication_set.name.casefold() == preset_name.casefold()
                    ),
                    None,
                )
                existing_set_id = existing_set.id if existing_set is not None else None

            command = _new_regimen_command(payload, existing_set_id=existing_set_id)
            service = WizardApplicationService(
                GetOrCreateUser(user_repository),
                CreateRegimen(regimen_repository, clock=utc_now),
                MaterializeSchedule(schedule_store, clock=utc_now),
                CreateMedicationSet(set_repository, clock=utc_now),
                AddRegimenToMedicationSet(set_repository),
                clock=utc_now,
            )
            saved = await service.save(telegram_user_id, command)
    except (WizardValidationError, StaleStartDateError, TimezoneRequiredError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except MedicationSetError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Не удалось обновить набор") from error
    return RegimenCreateResponse(events_count=saved.events_count)


@router.post("/regimens/{regimen_id}/edit-data", response_model=RegimenEditDataResponse)
async def regimen_edit_data(
    regimen_id: UUID,
    payload: RegimenListRequest,
    request: Request,
) -> RegimenEditDataResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
        try:
            await _ensure_personal_management(session, telegram_user_id)
            await ensure_recipient_cannot_manage_family_assignment(
                session, regimen_id=regimen_id, user_id=user.id
            )
        except FamilyAccessError as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
        context = await SqlAlchemyRegimenRevisionStore(session).get_context(
            user.id,
            regimen_id,
            effective_at=utc_now(),
        )
        if context is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Активное назначение не найдено")
        medication_sets = await ListMedicationSets(SqlAlchemyMedicationSetRepository(session))(
            user.id
        )
        current_set = _find_regimen_set(medication_sets, regimen_id)
        return _regimen_edit_data(context, current_set)


@router.post("/regimens/{regimen_id}/edit", response_model=RegimenEditResponse)
async def edit_regimen(
    regimen_id: UUID,
    payload: RegimenEditRequest,
    request: Request,
) -> RegimenEditResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
            await _ensure_personal_management(session, telegram_user_id)
            await ensure_recipient_cannot_manage_family_assignment(
                session, regimen_id=regimen_id, user_id=user.id
            )
            revision_store = SqlAlchemyRegimenRevisionStore(session)
            effective_at = utc_now()
            context = await revision_store.get_context(
                user.id,
                regimen_id,
                effective_at=effective_at,
            )
            if context is None:
                raise RegimenRevisionNotFoundError("Active regimen was not found")
            set_repository = SqlAlchemyMedicationSetRepository(session)
            medication_sets = await ListMedicationSets(set_repository)(user.id)
            current_set = _find_regimen_set(medication_sets, regimen_id)
            rule = _edited_schedule_rule(payload, current_set)
            remaining_intakes = (
                payload.remaining_intakes if payload.ending_kind == "total_intakes" else None
            )
            end_date = payload.end_date if payload.ending_kind == "end_date" else None
            if payload.ending_kind == "total_intakes" and remaining_intakes is None:
                raise WizardValidationError("Укажите оставшееся количество приёмов")
            if payload.ending_kind == "end_date" and end_date is None:
                raise WizardValidationError("Укажите дату завершения курса")
            revised = await ReviseRegimen(revision_store, clock=utc_now)(
                ReviseRegimenCommand(
                    user_id=user.id,
                    regimen_id=regimen_id,
                    effective_at=effective_at,
                    dose_amount=parse_dose_amount(payload.dose_amount),
                    meal_timing=(
                        MealTiming(payload.meal_timing) if payload.meal_timing is not None else None
                    ),
                    rule=rule,
                    remaining_intakes=remaining_intakes,
                    end_date=end_date,
                )
            )
            await _move_regimen_to_target(
                set_repository,
                user_id=user.id,
                regimen_id=regimen_id,
                timezone=revised.schedule.timezone,
                target=payload.reminder_target,
                medication_sets=medication_sets,
                current_set=current_set,
            )
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except RegimenRevisionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Активное назначение не найдено") from error
    except RemainingIntakesTooSmallError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Укажите не меньше {error.pending_count}: столько приёмов уже ожидают отметки",
        ) from error
    except NoFutureEventsError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "У курса нет будущих приёмов для изменения",
        ) from error
    except RegimenRevisionConflictError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Курс уже изменился. Обновите данные и попробуйте снова",
        ) from error
    except (WizardValidationError, RegimenRevisionError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except MedicationSetError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Не удалось обновить набор") from error
    return RegimenEditResponse(events_count=revised.events_count)


@router.post("/regimens/{regimen_id}/action", response_model=MiniAppRegimenResponse)
async def apply_regimen_action(
    regimen_id: UUID,
    payload: RegimenActionRequest,
    request: Request,
) -> MiniAppRegimenResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    target_status = {
        "pause": RegimenStatus.PAUSED,
        "resume": RegimenStatus.ACTIVE,
        "complete": RegimenStatus.COMPLETED,
    }[payload.action]
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with session_factory() as session, session.begin():
            user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
            await _ensure_personal_management(session, telegram_user_id)
            await ensure_recipient_cannot_manage_family_assignment(
                session, regimen_id=regimen_id, user_id=user.id
            )
            repository = SqlAlchemyRegimenRepository(session)
            regimen = await ChangeRegimenStatus(repository)(user.id, regimen_id, target_status)
            schedule = await SqlAlchemyScheduleMaterializationStore(session).get_active(regimen.id)
            next_event = (
                await SqlAlchemyIntakeEventRepository(session).next_pending_for_regimen(
                    user.id, regimen.id
                )
                if regimen.status is RegimenStatus.ACTIVE
                else None
            )
            response = _regimen_response(regimen, schedule, next_event)
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except RegimenNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Назначение не найдено") from error
    except (InvalidStatusTransitionError, RegimenUpdateConflictError) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return response


@router.post("/regimens/{regimen_id}/delete", response_model=RegimenDeleteResponse)
async def delete_regimen(
    regimen_id: UUID,
    payload: RegimenListRequest,
    request: Request,
) -> RegimenDeleteResponse:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
        try:
            await _ensure_personal_management(session, telegram_user_id)
            await ensure_recipient_cannot_manage_family_assignment(
                session, regimen_id=regimen_id, user_id=user.id
            )
        except FamilyAccessError as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
        repository = cast(RegimenDeletionRepository, SqlAlchemyRegimenRepository(session))
        deleted = await repository.delete_for_user(regimen_id, user.id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Назначение не найдено")
    return RegimenDeleteResponse(deleted=True)


def _authenticated_telegram_user_id(request: Request, init_data: str) -> int:
    settings: Settings = request.app.state.settings
    if settings.telegram_bot_token is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram bot is not configured")
    return validate_telegram_init_data(
        init_data,
        bot_token=settings.telegram_bot_token.get_secret_value(),
    )


async def _ensure_personal_management(
    session: AsyncSession,
    telegram_user_id: int,
) -> None:
    try:
        await FamilyService(
            session,
            GetOrCreateUser(SqlAlchemyUserRepository(session)),
        ).ensure_can_manage_personal_regimens(telegram_user_id)
    except FamilyAccessError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error


async def _build_authenticated_report(
    payload: ReportRequest,
    request: Request,
) -> MedicationReport:
    telegram_user_id = _authenticated_telegram_user_id(request, payload.init_data)
    return await _build_report_for_user(
        request,
        telegram_user_id=telegram_user_id,
        period=payload.period,
        regimen_id=payload.regimen_id,
    )


async def _build_report_for_user(
    request: Request,
    *,
    telegram_user_id: int,
    period: ReportPeriod,
    regimen_id: UUID | None,
) -> MedicationReport:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        user = await GetOrCreateUser(SqlAlchemyUserRepository(session))(telegram_user_id)
        if user.timezone is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Сначала настройте часовой пояс",
            )
        report = await build_medication_report(
            session,
            user_id=user.id,
            timezone=user.timezone,
            period=period,
            regimen_id=regimen_id,
        )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Назначение не найдено")
    return report


def _create_report_download_token(
    *,
    telegram_user_id: int,
    period: ReportPeriod,
    regimen_id: UUID | None,
    bot_token: str,
    now: datetime,
) -> str:
    payload = json.dumps(
        {
            "telegram_user_id": telegram_user_id,
            "period": period,
            "regimen_id": str(regimen_id) if regimen_id is not None else None,
            "expires_at": int((now + timedelta(minutes=5)).timestamp()),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    encoded = urlsafe_b64encode(payload).rstrip(b"=").decode()
    signature = hmac.new(
        bot_token.encode(),
        f"report-download:{encoded}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def _parse_report_download_token(
    token: str,
    *,
    bot_token: str,
    now: datetime,
) -> tuple[int, ReportPeriod, UUID | None]:
    if len(token) > 1024:
        raise ValueError("token is too long")
    try:
        encoded, signature = token.split(".", 1)
    except ValueError as error:
        raise ValueError("invalid token") from error
    expected = hmac.new(
        bot_token.encode(),
        f"report-download:{encoded}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid signature")
    try:
        padding = "=" * (-len(encoded) % 4)
        data = json.loads(b64decode(f"{encoded}{padding}", altchars=b"-_", validate=True).decode())
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("invalid payload") from error
    if not isinstance(data, dict):
        raise ValueError("invalid payload")
    telegram_user_id = data.get("telegram_user_id")
    period = data.get("period")
    expires_at = data.get("expires_at")
    regimen_value = data.get("regimen_id")
    if type(telegram_user_id) is not int or telegram_user_id <= 0:
        raise ValueError("invalid user")
    if period not in {"7", "30", "90", "all"}:
        raise ValueError("invalid period")
    if type(expires_at) is not int or expires_at < int(now.timestamp()):
        raise ValueError("expired token")
    try:
        regimen_id = UUID(regimen_value) if regimen_value is not None else None
    except (TypeError, ValueError) as error:
        raise ValueError("invalid regimen") from error
    return telegram_user_id, cast(ReportPeriod, period), regimen_id


def _report_response(report: MedicationReport) -> MedicationReportResponse:
    return MedicationReportResponse(
        timezone=report.timezone,
        period=report.period,
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=report.generated_at,
        summary=DashboardSummaryResponse(
            taken=report.summary.taken,
            skipped=report.summary.missed,
            pending=report.summary.pending,
            adherence_percent=report.summary.adherence_percent,
        ),
        courses=[
            ReportCourseResponse(
                id=item.id,
                medication_name=item.medication_name,
                medication_form=item.medication_form,
                dose_amount=item.dose_amount,
                dose_unit=item.dose_unit,
                start_date=item.start_date,
                status=item.status,
                total_intakes=item.total_intakes,
                taken=item.taken,
                missed=item.missed,
                pending=item.pending,
                remaining_to_target=item.remaining_to_target,
            )
            for item in report.courses
        ],
        events=[
            ReportEventResponse(
                scheduled_at=item.scheduled_at,
                resolved_at=item.resolved_at,
                medication_name=item.medication_name,
                dose_amount=item.dose_amount,
                dose_unit=item.dose_unit,
                status=item.status,
            )
            for item in report.events
        ],
        events_truncated=report.events_truncated,
    )


def _is_direct_local_request(request: Request, *, allow_docker_bridge: bool = False) -> bool:
    if request.client is None:
        return False
    if not allow_docker_bridge and request.client.host not in {"127.0.0.1", "::1"}:
        return False
    if request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False
    return not any(
        header in request.headers for header in ("forwarded", "x-forwarded-for", "cf-connecting-ip")
    )


def _signed_local_init_data(
    telegram_user_id: int,
    *,
    bot_token: str,
    now: datetime | None = None,
) -> str:
    current = now or datetime.now(UTC)
    values = {
        "auth_date": str(int(current.timestamp())),
        "query_id": "local-preview",
        "user": json.dumps({"id": telegram_user_id}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(
        secret,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


def _event_response(item: IntakeEventDetails) -> MiniAppEventResponse:
    return MiniAppEventResponse(
        id=item.event.id,
        medication_name=item.medication_name,
        medication_form=item.medication_form.value,
        dose_amount=_format_decimal(item.dose_amount),
        dose_unit=item.dose_unit,
        meal_timing=item.meal_timing,
        scheduled_at=item.event.scheduled_at,
        taken_at=item.event.taken_at,
        snoozed_until=item.event.snoozed_until,
        status=item.event.status,
    )


def _today_set_responses(
    medication_sets: list[MedicationSetDetails],
    details: list[IntakeEventDetails],
) -> list[MiniAppMedicationSetResponse]:
    responses: list[MiniAppMedicationSetResponse] = []
    for item in medication_sets:
        medication_set = item.medication_set
        if not medication_set.active:
            continue
        regimen_ids = {regimen.id for regimen in item.regimens}
        zone = ZoneInfo(medication_set.timezone)
        event_ids = [
            detail.event.id
            for detail in details
            if detail.event.regimen_id in regimen_ids
            and medication_set.window_start
            <= detail.event.scheduled_at.astimezone(zone).time()
            < medication_set.window_end
        ]
        if not event_ids:
            continue
        responses.append(
            MiniAppMedicationSetResponse(
                id=medication_set.id,
                name=medication_set.name,
                window_start=medication_set.window_start.strftime("%H:%M"),
                window_end=medication_set.window_end.strftime("%H:%M"),
                event_ids=event_ids,
            )
        )
    return responses


def _regimen_response(
    regimen: Regimen,
    schedule: StoredScheduleRule | None,
    next_event: IntakeEvent | None = None,
) -> MiniAppRegimenResponse:
    ending = "Без окончания"
    if regimen.total_intakes is not None:
        ending = f"{regimen.total_intakes} приёмов"
    elif regimen.end_date is not None:
        ending = f"До {regimen.end_date:%d.%m.%Y} включительно"
    return MiniAppRegimenResponse(
        id=regimen.id,
        medication_name=regimen.medication_name,
        medication_form=regimen.medication_form.value,
        dose_amount=_format_decimal(regimen.dose_amount),
        dose_unit=regimen.dose_unit,
        meal_timing=regimen.meal_timing,
        start_date=regimen.start_date,
        ending=ending,
        schedule=_format_schedule(schedule),
        intake_periods=_intake_periods(schedule),
        next_intake_at=next_event.scheduled_at if next_event is not None else None,
        status=regimen.status,
    )


def _format_schedule(schedule: StoredScheduleRule | None) -> str:
    if schedule is None:
        return "Расписание недоступно"
    rule = schedule.rule
    if isinstance(rule, DailyScheduleRule):
        return f"Ежедневно в {_format_times(rule.times)}"
    if isinstance(rule, IntervalScheduleRule):
        return f"Каждые {rule.every_days} дн. в {_format_times(rule.times)}"
    if isinstance(rule, WeekdayScheduleRule):
        weekdays = ", ".join(_WEEKDAYS[value - 1] for value in sorted(rule.weekdays))
        return f"{weekdays} в {_format_times(rule.times)}"
    if isinstance(rule, WeeklyScheduleRule):
        parts = [
            f"{_WEEKDAYS[weekday - 1]} в {_format_times(times)}"
            for weekday, times in rule.times_by_weekday
        ]
        return "; ".join(parts)
    return "Расписание недоступно"


def _intake_periods(
    schedule: StoredScheduleRule | None,
) -> list[Literal["early", "morning", "day", "evening"]]:
    if schedule is None:
        return ["early"]
    rule = schedule.rule
    if isinstance(rule, (DailyScheduleRule, IntervalScheduleRule, WeekdayScheduleRule)):
        values = rule.times
    elif isinstance(rule, WeeklyScheduleRule):
        values = tuple(value for _, times in rule.times_by_weekday for value in times)
    else:
        return ["early"]
    periods = {_intake_period(value) for value in values}
    return [value for value in ("early", "morning", "day", "evening") if value in periods]


def _intake_period(value: time) -> Literal["early", "morning", "day", "evening"]:
    if value < time(6):
        return "early"
    if value < time(11):
        return "morning"
    if value < time(18):
        return "day"
    return "evening"


_WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def _format_times(values: tuple[time, ...]) -> str:
    return ", ".join(value.strftime("%H:%M") for value in values)


def _summary(details: list[IntakeEventDetails]) -> DashboardSummaryResponse:
    taken = sum(item.event.status is IntakeEventStatus.TAKEN for item in details)
    skipped = sum(
        item.event.status in {IntakeEventStatus.SKIPPED, IntakeEventStatus.MISSED}
        for item in details
    )
    pending = len(details) - taken - skipped
    resolved = taken + skipped
    return DashboardSummaryResponse(
        taken=taken,
        skipped=skipped,
        pending=pending,
        adherence_percent=round(taken / resolved * 100) if resolved else None,
    )


def _format_decimal(value: Decimal) -> str:
    return (
        format(value, "f").rstrip("0").rstrip(".")
        if value != value.to_integral()
        else str(int(value))
    )


def _new_regimen_command(
    payload: RegimenCreateRequest,
    *,
    existing_set_id: UUID | None = None,
) -> NewRegimenCommand:
    schedule_kind = {
        "daily": ScheduleKind.DAILY,
        "interval": ScheduleKind.INTERVAL,
        "weekdays": ScheduleKind.WEEKDAYS,
    }[payload.schedule_kind]
    ending_kind = {
        "total_intakes": EndingKind.TOTAL_INTAKES,
        "end_date": EndingKind.END_DATE,
        "open_ended": EndingKind.OPEN_ENDED,
    }[payload.ending_kind]
    data: dict[str, object] = {
        "medication_name": payload.medication_name,
        "medication_form": payload.medication_form,
        "dose_amount": payload.dose_amount,
        "dose_unit": payload.dose_unit,
        "meal_timing": payload.meal_timing,
        "start_date": payload.start_date.strftime("%d.%m.%Y"),
        "schedule_kind": schedule_kind.value,
        "ending_kind": ending_kind.value,
        "weekdays": payload.weekdays,
    }
    if payload.every_days is not None:
        data["every_days"] = payload.every_days
    if payload.total_intakes is not None:
        data["total_intakes"] = payload.total_intakes
    if payload.end_date is not None:
        data["end_date"] = payload.end_date.strftime("%d.%m.%Y")

    if payload.reminder_target == "exact":
        data["reminder_mode"] = "exact"
        data["times"] = ", ".join(payload.times)
    else:
        name, window_start, window_end = MEDICATION_SET_PRESETS[payload.reminder_target]
        data.update(
            {
                "reminder_mode": "set",
                "medication_set_id": str(existing_set_id) if existing_set_id else None,
                "medication_set_name": name,
                "medication_set_window_start": window_start.strftime("%H:%M"),
                "medication_set_window_end": window_end.strftime("%H:%M"),
                "times": window_start.strftime("%H:%M"),
            }
        )
    return command_from_state(data)


def _regimen_edit_data(
    context: RevisionContext,
    current_set: MedicationSetDetails | None,
) -> RegimenEditDataResponse:
    rule = context.active_schedule.rule
    if isinstance(rule, DailyScheduleRule):
        schedule_kind: Literal["daily", "interval", "weekdays"] = "daily"
        every_days = None
        weekdays: list[int] = []
        times = rule.times
    elif isinstance(rule, IntervalScheduleRule):
        schedule_kind = "interval"
        every_days = rule.every_days
        weekdays = []
        times = rule.times
    elif isinstance(rule, WeekdayScheduleRule):
        schedule_kind = "weekdays"
        every_days = None
        weekdays = sorted(rule.weekdays)
        times = rule.times
    else:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Этот расширенный график пока можно изменить только в боте",
        )

    reminder_target, reminder_label = _current_reminder_target(current_set)
    regimen = context.regimen
    return RegimenEditDataResponse(
        id=regimen.id,
        medication_name=regimen.medication_name,
        medication_form=regimen.medication_form.value,
        dose_amount=_format_decimal(regimen.dose_amount),
        dose_unit=regimen.dose_unit,
        meal_timing=regimen.meal_timing,
        start_date=regimen.start_date,
        reminder_target=reminder_target,
        reminder_label=reminder_label,
        schedule_kind=schedule_kind,
        every_days=every_days,
        weekdays=weekdays,
        times=[value.strftime("%H:%M") for value in times],
        ending=_regimen_response(regimen, context.active_schedule).ending,
        remaining_intakes=context.replaceable_count + context.pending_count,
        minimum_remaining_intakes=context.pending_count,
        end_date=regimen.end_date,
    )


def _edited_schedule_rule(
    payload: RegimenEditRequest,
    current_set: MedicationSetDetails | None,
) -> ScheduleRule:
    times: tuple[time, ...]
    if payload.reminder_target in MEDICATION_SET_PRESETS:
        times = (MEDICATION_SET_PRESETS[payload.reminder_target][1],)
    elif payload.reminder_target == "keep" and current_set is not None:
        times = (current_set.medication_set.window_start,)
    else:
        times = parse_times(", ".join(payload.times))
    schedule_kind = {
        "daily": ScheduleKind.DAILY,
        "interval": ScheduleKind.INTERVAL,
        "weekdays": ScheduleKind.WEEKDAYS,
    }[payload.schedule_kind]
    return build_rule(
        schedule_kind,
        times,
        every_days=payload.every_days,
        weekdays=frozenset(payload.weekdays),
    )


def _find_regimen_set(
    medication_sets: list[MedicationSetDetails],
    regimen_id: UUID,
) -> MedicationSetDetails | None:
    return next(
        (
            details
            for details in medication_sets
            if any(regimen.id == regimen_id for regimen in details.regimens)
        ),
        None,
    )


def _current_reminder_target(
    current_set: MedicationSetDetails | None,
) -> tuple[Literal["morning", "day", "evening", "exact", "keep"], str]:
    if current_set is None:
        return "exact", "Точное время"
    name = current_set.medication_set.name
    for key, (preset_name, _, _) in MEDICATION_SET_PRESETS.items():
        if name.casefold() == preset_name.casefold():
            return key, preset_name  # type: ignore[return-value]
    return "keep", name


async def _refresh_bot_today(request: Request, telegram_user_id: int) -> None:
    settings: Settings = request.app.state.settings
    if settings.telegram_bot_token is None:
        return
    bot = Bot(
        settings.telegram_bot_token.get_secret_value(),
        session=AiohttpSession(timeout=5),
    )
    redis = Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=3
    )
    try:
        session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
        async with session_factory() as session:
            events = SqlAlchemyIntakeEventRepository(session)
            service = TelegramApplicationService(
                SqlAlchemyUserRepository(session),
                ListUserIntakeEventDetails(events),
                TransitionIntakeEvent(events, clock=utc_now),
                clock=utc_now,
                list_medication_sets=ListMedicationSets(SqlAlchemyMedicationSetRepository(session)),
            )
            text, markup = await service.today_screen(telegram_user_id)
        await SingleScreenRequestMiddleware(redis).refresh_current_screen(
            bot,
            chat_id=telegram_user_id,
            text=text,
            reply_markup=markup,
        )
    except TelegramAPIError as error:
        if "message is not modified" not in str(error).lower():
            logger.warning("Could not refresh bot screen after Mini App action", exc_info=True)
    except Exception:
        # A screen refresh must not turn a committed intake into an apparent save failure.
        logger.exception("Could not refresh bot screen after Mini App action")
    finally:
        await bot.session.close()
        await redis.aclose()


async def _clear_removed_family_messages(
    request: Request,
    removed: RemovedFamilyAccess,
) -> None:
    settings: Settings = request.app.state.settings
    if settings.telegram_bot_token is None:
        return
    bot = Bot(settings.telegram_bot_token.get_secret_value())
    try:
        await delete_family_reminder_messages(bot, removed.chats)
    finally:
        await bot.session.close()


async def _move_regimen_to_target(
    repository: SqlAlchemyMedicationSetRepository,
    *,
    user_id: UUID,
    regimen_id: UUID,
    timezone: str,
    target: Literal["morning", "day", "evening", "exact", "keep"],
    medication_sets: list[MedicationSetDetails],
    current_set: MedicationSetDetails | None,
) -> None:
    if target == "keep":
        return

    target_name = MEDICATION_SET_PRESETS[target][0] if target != "exact" else None
    if (
        current_set is not None
        and target_name is not None
        and current_set.medication_set.name.casefold() == target_name.casefold()
    ):
        return

    if current_set is not None:
        remaining_ids = tuple(
            regimen.id for regimen in current_set.regimens if regimen.id != regimen_id
        )
        value = current_set.medication_set
        if remaining_ids:
            await UpdateMedicationSet(repository, clock=utc_now)(
                UpdateMedicationSetCommand(
                    user_id=user_id,
                    set_id=value.id,
                    name=value.name,
                    window_start=value.window_start,
                    window_end=value.window_end,
                    regimen_ids=remaining_ids,
                )
            )
        else:
            await DeleteMedicationSet(repository)(user_id, value.id)

    if target == "exact":
        return
    name, window_start, window_end = MEDICATION_SET_PRESETS[target]
    destination = next(
        (
            details.medication_set
            for details in medication_sets
            if details is not current_set
            and details.medication_set.name.casefold() == name.casefold()
        ),
        None,
    )
    if destination is not None:
        await AddRegimenToMedicationSet(repository)(user_id, destination.id, regimen_id)
        return
    await CreateMedicationSet(repository, clock=utc_now)(
        CreateMedicationSetCommand(
            user_id=user_id,
            name=name,
            window_start=window_start,
            window_end=window_end,
            timezone=timezone,
            regimen_ids=(regimen_id,),
        )
    )


def validate_telegram_init_data(
    init_data: str,
    *,
    bot_token: str,
    now: datetime | None = None,
    max_age_seconds: int = 600,
) -> int:
    values = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram signature is missing")
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_hash, calculated_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram signature is invalid")

    current = now or datetime.now(UTC)
    try:
        auth_date = datetime.fromtimestamp(int(values["auth_date"]), UTC)
        user_data = json.loads(values["user"])
        telegram_user_id = int(user_data["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram identity is invalid") from error
    age = (current - auth_date).total_seconds()
    if age < -30 or age > max_age_seconds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram authorization has expired")
    if telegram_user_id <= 0:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram identity is invalid")
    return telegram_user_id
