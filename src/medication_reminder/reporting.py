from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medication_reminder.intake_events.infrastructure.models import IntakeEventModel
from medication_reminder.regimens.infrastructure.models import RegimenModel

ReportPeriod = Literal["7", "30", "90", "all"]

_PENDING_STATUSES = ("scheduled", "due", "snoozed")
_MISSED_STATUSES = ("skipped", "missed")
_REGIMEN_STATUS_LABELS = {
    "active": "Активен",
    "paused": "На паузе",
    "completed": "Завершён",
}


@dataclass(frozen=True, slots=True)
class ReportSummary:
    taken: int
    missed: int
    pending: int
    adherence_percent: int | None


@dataclass(frozen=True, slots=True)
class ReportCourse:
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

    @property
    def remaining_to_target(self) -> int | None:
        if self.total_intakes is None:
            return None
        return max(self.total_intakes - self.taken, 0)


@dataclass(frozen=True, slots=True)
class ReportEvent:
    scheduled_at: datetime
    resolved_at: datetime | None
    medication_name: str
    dose_amount: str
    dose_unit: str
    status: str


@dataclass(frozen=True, slots=True)
class MedicationReport:
    timezone: str
    period: ReportPeriod
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    summary: ReportSummary
    courses: tuple[ReportCourse, ...]
    events: tuple[ReportEvent, ...]
    events_truncated: bool


async def build_medication_report(
    session: AsyncSession,
    *,
    user_id: UUID,
    timezone: str,
    period: ReportPeriod,
    regimen_id: UUID | None = None,
    now: datetime | None = None,
) -> MedicationReport | None:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    zone = ZoneInfo(timezone)
    regimen_statement = select(RegimenModel).where(RegimenModel.user_id == user_id)
    if regimen_id is not None:
        regimen_statement = regimen_statement.where(RegimenModel.id == regimen_id)
    regimen_statement = regimen_statement.order_by(RegimenModel.created_at.desc()).limit(50)
    regimens = list((await session.scalars(regimen_statement)).all())
    if regimen_id is not None and not regimens:
        return None

    local_today = current.astimezone(zone).date()
    if period == "all":
        first_date = min((item.start_date for item in regimens), default=local_today)
    else:
        first_date = local_today - timedelta(days=int(period) - 1)
    period_start = datetime.combine(first_date, time.min, zone).astimezone(UTC)
    period_end = datetime.combine(local_today + timedelta(days=1), time.min, zone).astimezone(UTC)
    regimen_ids = [item.id for item in regimens]

    counts: dict[UUID, tuple[int, int, int]] = {}
    if regimen_ids:
        lifetime_rows = (
            await session.execute(
                select(
                    IntakeEventModel.regimen_id,
                    func.count().filter(IntakeEventModel.status == "taken"),
                    func.count().filter(IntakeEventModel.status.in_(_MISSED_STATUSES)),
                    func.count().filter(IntakeEventModel.status.in_(_PENDING_STATUSES)),
                )
                .where(IntakeEventModel.regimen_id.in_(regimen_ids))
                .group_by(IntakeEventModel.regimen_id)
            )
        ).all()
        counts = {row.regimen_id: (int(row[1]), int(row[2]), int(row[3])) for row in lifetime_rows}

    courses = tuple(
        ReportCourse(
            id=item.id,
            medication_name=item.medication_name,
            medication_form=item.medication_form,
            dose_amount=_format_decimal(item.dose_amount),
            dose_unit=item.dose_unit,
            start_date=item.start_date,
            status=item.status,
            total_intakes=item.total_intakes,
            taken=counts.get(item.id, (0, 0, 0))[0],
            missed=counts.get(item.id, (0, 0, 0))[1],
            pending=counts.get(item.id, (0, 0, 0))[2],
        )
        for item in regimens
    )

    summary = ReportSummary(taken=0, missed=0, pending=0, adherence_percent=None)
    events: tuple[ReportEvent, ...] = ()
    truncated = False
    if regimen_ids:
        event_filter = (
            IntakeEventModel.regimen_id.in_(regimen_ids),
            IntakeEventModel.scheduled_at >= period_start,
            IntakeEventModel.scheduled_at < period_end,
            IntakeEventModel.status != "cancelled",
        )
        summary_row = (
            await session.execute(
                select(
                    func.count().filter(IntakeEventModel.status == "taken"),
                    func.count().filter(IntakeEventModel.status.in_(_MISSED_STATUSES)),
                    func.count().filter(IntakeEventModel.status.in_(_PENDING_STATUSES)),
                ).where(*event_filter)
            )
        ).one()
        taken, missed, pending = (int(summary_row[0]), int(summary_row[1]), int(summary_row[2]))
        resolved = taken + missed
        summary = ReportSummary(
            taken=taken,
            missed=missed,
            pending=pending,
            adherence_percent=round(taken / resolved * 100) if resolved else None,
        )
        event_models = list(
            (
                await session.scalars(
                    select(IntakeEventModel)
                    .where(*event_filter)
                    .order_by(IntakeEventModel.scheduled_at.desc())
                    .limit(1001)
                )
            ).all()
        )
        truncated = len(event_models) > 1000
        events = tuple(
            ReportEvent(
                scheduled_at=item.scheduled_at,
                resolved_at=item.resolved_at if item.status == "taken" else None,
                medication_name=item.medication_name,
                dose_amount=_format_decimal(item.dose_amount),
                dose_unit=item.dose_unit,
                status=item.status,
            )
            for item in event_models[:1000]
        )

    return MedicationReport(
        timezone=timezone,
        period=period,
        period_start=period_start,
        period_end=period_end,
        generated_at=current,
        summary=summary,
        courses=courses,
        events=events,
        events_truncated=truncated,
    )


def render_medication_report_pdf(report: MedicationReport) -> bytes:
    regular_font, bold_font = _register_pdf_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=17 * mm,
        title="Отчёт о приёме препаратов",
        author="Вовремя",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=19,
        leading=23,
        textColor=colors.HexColor("#0B6174"),
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#16333A"),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334B51"),
    )
    small_style = ParagraphStyle(
        "ReportSmall",
        parent=body_style,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#667A7F"),
    )
    local_zone = ZoneInfo(report.timezone)
    date_end = (report.period_end - timedelta(microseconds=1)).astimezone(local_zone).date()
    story = [
        Paragraph("Отчёт о приёме препаратов", title_style),
        Paragraph(
            f"Период: {report.period_start.astimezone(local_zone):%d.%m.%Y}–{date_end:%d.%m.%Y}"
            f" · часовой пояс {report.timezone}",
            small_style,
        ),
        Spacer(1, 4 * mm),
        _summary_table(report.summary, regular_font, bold_font),
        Paragraph("Прогресс за весь курс", heading_style),
    ]
    if report.courses:
        story.append(_courses_table(report.courses, regular_font, bold_font, body_style))
    else:
        story.append(Paragraph("Назначений за выбранный период нет.", body_style))

    story.extend(
        [
            Spacer(1, 5 * mm),
            Paragraph("Подробная история приёмов доступна в приложении.", small_style),
            Paragraph(
                "Сформировано по отметкам пользователя. "
                "Документ не является медицинским заключением.",
                small_style,
            ),
        ]
    )
    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _summary_table(summary: ReportSummary, regular_font: str, bold_font: str) -> Table:
    adherence = "—" if summary.adherence_percent is None else f"{summary.adherence_percent}%"
    table = Table(
        [
            ["Принято", "Пропущено", "Ожидает", "Соблюдение"],
            [str(summary.taken), str(summary.missed), str(summary.pending), adherence],
        ],
        colWidths=[42 * mm] * 4,
        rowHeights=[7 * mm, 10 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F3F4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#557076")),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#16333A")),
                ("FONTNAME", (0, 0), (-1, 0), regular_font),
                ("FONTNAME", (0, 1), (-1, 1), bold_font),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                ("FONTSIZE", (0, 1), (-1, 1), 13),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7DADC")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7DADC")),
            ]
        )
    )
    return table


def _courses_table(
    courses: tuple[ReportCourse, ...],
    regular_font: str,
    bold_font: str,
    body_style: ParagraphStyle,
) -> Table:
    rows = [
        [
            Paragraph(
                label,
                ParagraphStyle(
                    "CourseHeader",
                    parent=body_style,
                    fontName=bold_font,
                    textColor=colors.white,
                ),
            )
            for label in (
                "Препарат / доза",
                "Начало",
                "Принято",
                "Пропущено",
                "Осталось<br/>до цели",
            )
        ]
    ]
    for course in courses:
        progress = str(course.taken)
        if course.total_intakes is not None:
            progress = f"{course.taken} из {course.total_intakes}"
        status = _REGIMEN_STATUS_LABELS.get(course.status, course.status)
        rows.append(
            [
                Paragraph(
                    f"{escape(course.medication_name)}<br/>"
                    f"{escape(course.dose_amount)} {escape(course.dose_unit)} · {escape(status)}",
                    body_style,
                ),
                Paragraph(course.start_date.strftime("%d.%m.%Y"), body_style),
                Paragraph(progress, body_style),
                Paragraph(str(course.missed), body_style),
                Paragraph(
                    str(course.remaining_to_target)
                    if course.remaining_to_target is not None
                    else "—",
                    body_style,
                ),
            ]
        )
    table = Table(rows, colWidths=[66 * mm, 25 * mm, 27 * mm, 25 * mm, 25 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), regular_font),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                ("LEADING", (0, 0), (-1, -1), 8.7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B6174")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334B51")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F9F9")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5E2E4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _register_pdf_fonts() -> tuple[str, str]:
    candidates = (
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ),
    )
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            if "VovremyaRegular" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("VovremyaRegular", str(regular)))
                pdfmetrics.registerFont(TTFont("VovremyaBold", str(bold)))
            return "VovremyaRegular", "VovremyaBold"
    raise RuntimeError("Не найден шрифт для создания PDF")


def _page_footer(canvas: Any, document: SimpleDocTemplate) -> None:
    pdf_canvas = canvas
    pdf_canvas.saveState()
    pdf_canvas.setFont("VovremyaRegular", 7)
    pdf_canvas.setFillColor(colors.HexColor("#7A8D91"))
    pdf_canvas.drawString(16 * mm, 9 * mm, "Вовремя")
    pdf_canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Страница {document.page}")
    pdf_canvas.restoreState()


def _format_decimal(value: Decimal) -> str:
    return (
        format(value, "f").rstrip("0").rstrip(".")
        if value != value.to_integral()
        else str(int(value))
    )
