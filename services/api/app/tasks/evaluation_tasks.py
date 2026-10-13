"""
Background evaluation. Triggered by interview_service._maybe_advance
when an interview reaches COMPLETED (end of the HR round) — evaluation
runs as a background job, not inline on the request that completes
the interview, per the spec's "long-running AI work should not block
HTTP requests" instruction.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.extensions import celery, db
from app.models import Interview, InterviewStatus
from app.services.evaluation_service import EvaluationService

logger = logging.getLogger("app.tasks.evaluation")


@celery.task(name="evaluation.evaluate_interview", bind=True, max_retries=2)
def evaluate_interview_task(self, interview_id: str) -> None:
    interview = db.session.get(Interview, uuid.UUID(interview_id))
    if interview is None:
        logger.warning("evaluate_interview_task: interview %s not found", interview_id)
        return
    if interview.status != InterviewStatus.COMPLETED:
        # Already evaluated, cancelled, or otherwise not eligible —
        # avoid re-running on a retry/duplicate enqueue.
        logger.info(
            "evaluate_interview_task: interview %s is '%s', not 'completed' — skipping",
            interview_id, interview.status,
        )
        return

    interview.status = InterviewStatus.EVALUATING
    db.session.commit()

    try:
        EvaluationService().evaluate_interview(interview.id)
    except Exception as exc:  # noqa: BLE001 — last-resort guard for a background job
        logger.exception("Unexpected error evaluating interview %s", interview_id)
        interview.status = InterviewStatus.FAILED
        interview.evaluation_error = f"Unexpected error: {exc}"[:2000]
        db.session.commit()
        return

    interview.status = InterviewStatus.REPORT_GENERATING
    interview.evaluated_at = datetime.now(timezone.utc)
    interview.evaluation_error = None
    db.session.commit()

    from app.tasks.report_tasks import generate_report_task

    generate_report_task.delay(str(interview.id))
