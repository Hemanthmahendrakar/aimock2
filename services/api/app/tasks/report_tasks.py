"""
Background report generation. Triggered from evaluation_tasks.py right
after an interview reaches REPORT_GENERATING (immediately following
successful evaluation) — a separate task, not folded into
evaluate_interview_task, so a report can be regenerated independently
later (e.g. after switching AI_PROVIDER) without re-running evaluation.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.extensions import celery, db
from app.models import Interview, InterviewStatus
from app.services.report_service import ReportService, ReportServiceError

logger = logging.getLogger("app.tasks.report")


@celery.task(name="report.generate_report", bind=True, max_retries=2)
def generate_report_task(self, interview_id: str) -> None:
    interview = db.session.get(Interview, uuid.UUID(interview_id))
    if interview is None:
        logger.warning("generate_report_task: interview %s not found", interview_id)
        return
    if interview.status != InterviewStatus.REPORT_GENERATING:
        logger.info(
            "generate_report_task: interview %s is '%s', not 'report_generating' — skipping",
            interview_id, interview.status,
        )
        return

    try:
        ReportService().generate_report(interview.id)
    except ReportServiceError as exc:
        logger.warning("Report generation failed for interview %s: %s", interview_id, exc)
        interview.status = InterviewStatus.FAILED
        interview.report_generation_error = str(exc)[:2000]
        db.session.commit()
        return
    except Exception as exc:  # noqa: BLE001 — last-resort guard for a background job
        logger.exception("Unexpected error generating report for interview %s", interview_id)
        interview.status = InterviewStatus.FAILED
        interview.report_generation_error = f"Unexpected error: {exc}"[:2000]
        db.session.commit()
        return

    interview.status = InterviewStatus.REPORT_READY
    interview.report_generated_at = datetime.now(timezone.utc)
    interview.report_generation_error = None
    db.session.commit()
