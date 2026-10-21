"""
Interview template routes. institute_id always comes from
g.current_institute_id — no route here accepts institute_id as input.
"""
import uuid

from flask import Blueprint, request, g
from pydantic import ValidationError

from app.models import RoleName
from app.schemas.interview_template_schemas import (
    CreateInterviewTemplateRequest,
    UpdateInterviewTemplateRequest,
)
from app.schemas.serializers import serialize_interview_template
from app.services.interview_template_service import (
    InterviewTemplateService,
    InterviewTemplateServiceError,
)
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint(
    "interview_templates", __name__, url_prefix="/api/v1/institute/interview-templates"
)


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
def create_template():
    try:
        payload = CreateInterviewTemplateRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = InterviewTemplateService()
    try:
        template = service.create(g.current_institute_id, data=payload.model_dump())
    except InterviewTemplateServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_interview_template(template), status=201)


@bp.get("")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_templates():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    service = InterviewTemplateService()
    templates, total = service.list(
        institute_id=g.current_institute_id, page=page, per_page=per_page
    )

    return ok(
        {
            "items": [serialize_interview_template(t) for t in templates],
            "pagination": {
                "page": max(page, 1),
                "per_page": min(max(per_page, 1), 100),
                "total": total,
            },
        }
    )


@bp.get("/<template_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_template(template_id: str):
    parsed_id = _parse_uuid_or_none(template_id)
    if parsed_id is None:
        return error("not_found", "Interview template not found.", 404)

    service = InterviewTemplateService()
    try:
        template = service.get(parsed_id, institute_id=g.current_institute_id)
    except InterviewTemplateServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_interview_template(template))


@bp.patch("/<template_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def update_template(template_id: str):
    parsed_id = _parse_uuid_or_none(template_id)
    if parsed_id is None:
        return error("not_found", "Interview template not found.", 404)

    try:
        payload = UpdateInterviewTemplateRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = InterviewTemplateService()
    try:
        template = service.update(
            parsed_id,
            institute_id=g.current_institute_id,
            data=payload.model_dump(exclude_unset=True),
        )
    except InterviewTemplateServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_interview_template(template))


@bp.delete("/<template_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def delete_template(template_id: str):
    parsed_id = _parse_uuid_or_none(template_id)
    if parsed_id is None:
        return error("not_found", "Interview template not found.", 404)

    service = InterviewTemplateService()
    try:
        service.delete(parsed_id, institute_id=g.current_institute_id)
    except InterviewTemplateServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok({"message": "Interview template removed."})
