"""
Institute-admin read/cancel access to interviews. institute_id always
comes from g.current_institute_id — InterviewService.get_for_admin
scopes every lookup by it, so an admin can never view or cancel
another institute's interview by guessing an ID.
"""
import uuid

from flask import Blueprint, g

from app.models import RoleName
from app.schemas.serializers_interview import serialize_interview_admin
from app.schemas.serializers_report import serialize_report
from app.services.interview_service import InterviewService, InterviewServiceError
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.report_repository import ReportRepository
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint("institute_interviews", __name__, url_prefix="/api/v1/institute/interviews")


def _parse_uuid_or_none(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        return None


@bp.get("/<interview_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_interview(interview_id: str):
    parsed_id = _parse_uuid_or_none(interview_id)
    if parsed_id is None:
        return error("not_found", "Interview not found.", 404)

    service = InterviewService()
    try:
        interview = service.get_for_admin(parsed_id, institute_id=g.current_institute_id)
    except InterviewServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    evaluations = EvaluationRepository().list_for_interview(interview.id)
    return ok(serialize_interview_admin(interview, evaluations=evaluations))


@bp.get("/<interview_id>/report")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_interview_report(interview_id: str):
    parsed_id = _parse_uuid_or_none(interview_id)
    if parsed_id is None:
        return error("not_found", "Interview not found.", 404)

    service = InterviewService()
    try:
        interview = service.get_for_admin(parsed_id, institute_id=g.current_institute_id)
    except InterviewServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    report = ReportRepository().get_by_interview_scoped(
        interview.id, institute_id=g.current_institute_id
    )
    if report is None or report.current_version is None:
        return error(
            "report_not_ready",
            "This interview's report hasn't been generated yet.",
            404,
        )

    return ok(serialize_report(report))


@bp.post("/<interview_id>/cancel")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def cancel_interview(interview_id: str):
    parsed_id = _parse_uuid_or_none(interview_id)
    if parsed_id is None:
        return error("not_found", "Interview not found.", 404)

    service = InterviewService()
    try:
        interview = service.cancel(parsed_id, institute_id=g.current_institute_id)
    except InterviewServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_interview_admin(interview))
