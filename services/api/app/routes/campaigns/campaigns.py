"""
Campaign routes. institute_id always comes from g.current_institute_id
— no route here accepts institute_id as client input.
"""
import uuid

from flask import Blueprint, request, g
from pydantic import ValidationError

from app.models import RoleName, CampaignStatus
from app.schemas.campaign_schemas import (
    CreateCampaignRequest,
    UpdateCampaignRequest,
    AssignStudentsRequest,
)
from app.schemas.serializers import serialize_campaign, serialize_student
from app.schemas.serializers_interview import serialize_interview_summary
from app.services.campaign_service import CampaignService, CampaignServiceError
from app.services.interview_service import InterviewService
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint("campaigns", __name__, url_prefix="/api/v1/institute/campaigns")


def _validation_error_response(exc: ValidationError):
    details = [
        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return error("validation_error", "Invalid request data.", 422, details=details)


def _parse_uuid_or_none(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        return None


@bp.post("")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def create_campaign():
    try:
        payload = CreateCampaignRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = CampaignService()
    try:
        campaign = service.create(g.current_institute_id, data=payload.model_dump())
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_campaign(campaign, assigned_student_count=0), status=201)


@bp.get("")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_campaigns():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)
    status = request.args.get("status") or None

    service = CampaignService()
    campaigns, total = service.list(
        institute_id=g.current_institute_id, page=page, per_page=per_page, status=status
    )

    return ok(
        {
            "items": [serialize_campaign(c) for c in campaigns],
            "pagination": {
                "page": max(page, 1),
                "per_page": min(max(per_page, 1), 100),
                "total": total,
            },
        }
    )


@bp.get("/<campaign_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_campaign(campaign_id: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    service = CampaignService()
    try:
        campaign = service.get(parsed_id, institute_id=g.current_institute_id)
        _, assigned_count = service.list_assigned_students(
            parsed_id, institute_id=g.current_institute_id, page=1, per_page=1
        )
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_campaign(campaign, assigned_student_count=assigned_count))


@bp.patch("/<campaign_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def update_campaign(campaign_id: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    try:
        payload = UpdateCampaignRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = CampaignService()
    try:
        campaign = service.update(
            parsed_id,
            institute_id=g.current_institute_id,
            data=payload.model_dump(exclude_none=True),
        )
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_campaign(campaign))


@bp.delete("/<campaign_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def delete_campaign(campaign_id: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    service = CampaignService()
    try:
        service.delete(parsed_id, institute_id=g.current_institute_id)
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok({"message": "Campaign removed."})


def _transition(campaign_id: str, target_status: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    service = CampaignService()
    try:
        campaign = service.transition_status(
            parsed_id, institute_id=g.current_institute_id, target_status=target_status
        )
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_campaign(campaign))


@bp.post("/<campaign_id>/activate")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def activate_campaign(campaign_id: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    campaign_service = CampaignService()
    try:
        campaign = campaign_service.transition_status(
            parsed_id, institute_id=g.current_institute_id, target_status=CampaignStatus.ACTIVE
        )
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    # Activating a campaign assigns interviews to everyone currently on
    # its roster — see InterviewService.create_interviews_for_campaign
    # for why this is safe to run more than once.
    interview_summary = InterviewService().create_interviews_for_campaign(
        campaign, institute_id=g.current_institute_id
    )

    result = serialize_campaign(campaign)
    result["interviews_created"] = interview_summary["created"]
    return ok(result)


@bp.post("/<campaign_id>/complete")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def complete_campaign(campaign_id: str):
    return _transition(campaign_id, CampaignStatus.COMPLETED)


@bp.post("/<campaign_id>/archive")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def archive_campaign(campaign_id: str):
    return _transition(campaign_id, CampaignStatus.ARCHIVED)


# ------------------------------------------------------------------
# Roster
# ------------------------------------------------------------------
@bp.post("/<campaign_id>/students")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def assign_students(campaign_id: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    try:
        payload = AssignStudentsRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = CampaignService()
    try:
        result = service.assign_students(
            parsed_id, institute_id=g.current_institute_id, student_ids=payload.student_ids
        )
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(result)


@bp.get("/<campaign_id>/students")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_campaign_students(campaign_id: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    service = CampaignService()
    try:
        students, total = service.list_assigned_students(
            parsed_id, institute_id=g.current_institute_id, page=page, per_page=per_page
        )
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(
        {
            "items": [serialize_student(s) for s in students],
            "pagination": {
                "page": max(page, 1),
                "per_page": min(max(per_page, 1), 100),
                "total": total,
            },
        }
    )


@bp.delete("/<campaign_id>/students/<student_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def unassign_student(campaign_id: str, student_id: str):
    parsed_campaign_id = _parse_uuid_or_none(campaign_id)
    parsed_student_id = _parse_uuid_or_none(student_id)
    if parsed_campaign_id is None or parsed_student_id is None:
        return error("not_found", "Not found.", 404)

    service = CampaignService()
    try:
        service.unassign_student(
            parsed_campaign_id, parsed_student_id, institute_id=g.current_institute_id
        )
    except CampaignServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok({"message": "Student unassigned."})


# ------------------------------------------------------------------
# Interviews (created automatically on activation — see activate_campaign)
# ------------------------------------------------------------------
@bp.get("/<campaign_id>/interviews")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_campaign_interviews(campaign_id: str):
    parsed_id = _parse_uuid_or_none(campaign_id)
    if parsed_id is None:
        return error("not_found", "Campaign not found.", 404)

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    service = InterviewService()
    interviews, total = service.list_for_campaign(
        parsed_id, institute_id=g.current_institute_id, page=page, per_page=per_page
    )

    return ok(
        {
            "items": [serialize_interview_summary(i) for i in interviews],
            "pagination": {
                "page": max(page, 1),
                "per_page": min(max(per_page, 1), 100),
                "total": total,
            },
        }
    )
