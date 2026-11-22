from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from medication_reminder.reporting import (
    MedicationReport,
    ReportCourse,
    ReportEvent,
    ReportSummary,
    render_medication_report_pdf,
)


def test_course_progress_never_becomes_negative() -> None:
    course = ReportCourse(
        id=uuid4(),
        medication_name="Железо",
        medication_form="tablet",
        dose_amount="1",
        dose_unit="таблетка",
        start_date=date(2026, 10, 1),
        status="active",
        total_intakes=2,
        taken=3,
        missed=0,
        pending=0,
    )

    assert course.remaining_to_target == 0


def test_pdf_report_contains_a_pdf_document() -> None:
    generated_at = datetime(2026, 10, 24, 12, tzinfo=UTC)
    report = MedicationReport(
        timezone="Europe/Moscow",
        period="30",
        period_start=generated_at - timedelta(days=29),
        period_end=generated_at + timedelta(days=1),
        generated_at=generated_at,
        summary=ReportSummary(taken=12, missed=2, pending=21, adherence_percent=86),
        courses=(
            ReportCourse(
                id=uuid4(),
                medication_name="Препарат для уколов",
                medication_form="injection",
                dose_amount="1",
                dose_unit="мг",
                start_date=date(2026, 9, 25),
                status="active",
                total_intakes=35,
                taken=12,
                missed=2,
                pending=21,
            ),
        ),
        events=(
            ReportEvent(
                scheduled_at=generated_at - timedelta(hours=2),
                resolved_at=generated_at - timedelta(hours=1, minutes=47),
                medication_name="Препарат для уколов",
                dose_amount="1",
                dose_unit="мг",
                status="taken",
            ),
        ),
        events_truncated=False,
    )

    result = render_medication_report_pdf(report)

    assert result.startswith(b"%PDF-")
    assert len(result) > 10_000

    large_history = render_medication_report_pdf(replace(report, events=report.events * 1000))
    assert abs(len(large_history) - len(result)) < 100
