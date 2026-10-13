"""
Resume routes, nested under a student. institute_id always comes from
g.current_institute_id; student_id is validated as belonging to that
institute before any resume operation proceeds (see ResumeService).
"""
import uuid

from flask import Blueprint, request, g

from app.models import RoleName
from app.schemas.serializers_resume import serialize_resume_version
from app.services.resume_service import ResumeService, ResumeServiceError
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint("resumes", __name__, url_prefix="/api/v1/institute/students/<student_id>/resume")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024 + 1024  # small buffer over the 5MB resume limit


def _parse_uuid_or_none(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        return None


@bp.post("")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def upload_resume(student_id: str):
    parsed_student_id = _parse_uuid_or_none(student_id)
    if parsed_student_id is None:
        return error("not_found", "Student not found.", 404)

    if "file" not in request.files:
        return error("missing_file", "No file was uploaded (expected field 'file').", 422)
    file = request.files["file"]
    if not file.filename:
        return error("missing_file", "No file was uploaded.", 422)

    data = file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return error("file_too_large", "File exceeds the maximum allowed size.", 422)

    service = ResumeService()
    try:
        version = service.upload(
            institute_id=g.current_institute_id,
            student_id=parsed_student_id,
            filename=file.filename,
            data=data,
        )
    except ResumeServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_resume_version(version), status=201)


@bp.get("")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_current_resume(student_id: str):
    parsed_student_id = _parse_uuid_or_none(student_id)
    if parsed_student_id is None:
        return error("not_found", "Student not found.", 404)

    service = ResumeService()
    try:
        version = service.get_current(parsed_student_id, institute_id=g.current_institute_id)
    except ResumeServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_resume_version(version))


@bp.get("/versions")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_resume_versions(student_id: str):
    parsed_student_id = _parse_uuid_or_none(student_id)
    if parsed_student_id is None:
        return error("not_found", "Student not found.", 404)

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    service = ResumeService()
    try:
        versions, total = service.list_versions(
            parsed_student_id, institute_id=g.current_institute_id, page=page, per_page=per_page
        )
    except ResumeServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(
        {
            "items": [serialize_resume_version(v, include_profile=False) for v in versions],
            "pagination": {
                "page": max(page, 1),
                "per_page": min(max(per_page, 1), 100),
                "total": total,
            },
        }
    )


@bp.get("/versions/<version_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_resume_version(student_id: str, version_id: str):
    parsed_student_id = _parse_uuid_or_none(student_id)
    parsed_version_id = _parse_uuid_or_none(version_id)
    if parsed_student_id is None or parsed_version_id is None:
        return error("not_found", "Not found.", 404)

    service = ResumeService()
    try:
        version = service.get_version(
            parsed_student_id, parsed_version_id, institute_id=g.current_institute_id
        )
    except ResumeServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_resume_version(version))
