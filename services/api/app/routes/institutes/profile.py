"""
Institute profile/branding/logo routes. Every handler here derives the
institute solely from g.current_institute_id (set by
require_institute_scope from the authenticated session) — request data
is never used to pick which institute is being read or written.
"""
from flask import Blueprint, request, g
from pydantic import ValidationError

from app.models import RoleName
from app.schemas.institute_schemas import UpdateInstituteProfileRequest, UpdateBrandingRequest
from app.services.institute_service import InstituteService, InstituteServiceError
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint("institute_profile", __name__, url_prefix="/api/v1/institute")

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 + 1024  # small buffer over the 2MB logo limit


def _validation_error_response(exc: ValidationError):
    details = [
        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return error("validation_error", "Invalid request data.", 422, details=details)


@bp.get("/profile")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_profile():
    profile = InstituteService().get_profile(g.current_institute_id)
    return ok(profile)


@bp.patch("/profile")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def update_profile():
    try:
        payload = UpdateInstituteProfileRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = InstituteService()
    try:
        profile = service.update_profile(
            g.current_institute_id,
            name=payload.name,
            phone=payload.phone,
            address=payload.address,
            website=payload.website,
        )
    except InstituteServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(profile)


@bp.put("/branding")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def update_branding():
    try:
        payload = UpdateBrandingRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = InstituteService()
    try:
        profile = service.update_branding(
            g.current_institute_id,
            branding={
                "primary_color": payload.primary_color,
                "secondary_color": payload.secondary_color,
            },
        )
    except InstituteServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(profile)


@bp.post("/logo")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def upload_logo():
    if "file" not in request.files:
        return error("missing_file", "No file was uploaded (expected field 'file').", 422)

    file = request.files["file"]
    if not file.filename:
        return error("missing_file", "No file was uploaded.", 422)

    data = file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return error("file_too_large", "File exceeds the maximum allowed size.", 422)

    service = InstituteService()
    try:
        profile = service.upload_logo(
            g.current_institute_id, filename=file.filename, data=data
        )
    except InstituteServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(profile)


@bp.delete("/logo")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def delete_logo():
    service = InstituteService()
    try:
        profile = service.delete_logo(g.current_institute_id)
    except InstituteServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(profile)
