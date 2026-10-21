"""
Student management routes. institute_id always comes from
g.current_institute_id (set by require_institute_scope) — no route
here accepts institute_id as input, so there's no spoofing surface.
"""
import uuid

from flask import Blueprint, request, g
from pydantic import ValidationError

from app.models import RoleName
from app.schemas.student_schemas import CreateStudentRequest, UpdateStudentRequest
from app.schemas.serializers import serialize_student
from app.services.student_service import StudentService, StudentServiceError
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint("students", __name__, url_prefix="/api/v1/institute/students")

MAX_CSV_UPLOAD_BYTES = 5 * 1024 * 1024 + 1024


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
def create_student():
    try:
        payload = CreateStudentRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = StudentService()
    try:
        student = service.create(
            g.current_institute_id,
            name=payload.name,
            email=payload.email,
            roll_number=payload.roll_number,
            department=payload.department,
            batch=payload.batch,
            phone=payload.phone,
            campus_id=payload.campus_id,
            course=payload.course,
            graduation_year=payload.graduation_year,
            experience_level=payload.experience_level,
        )
    except StudentServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_student(student), status=201)


@bp.get("")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_students():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)
    search = request.args.get("search") or None
    department = request.args.get("department") or None
    batch = request.args.get("batch") or None
    status = request.args.get("status") or None

    service = StudentService()
    students, total = service.list(
        institute_id=g.current_institute_id,
        page=page,
        per_page=per_page,
        search=search,
        department=department,
        batch=batch,
        status=status,
    )

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


@bp.get("/<student_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_student(student_id: str):
    parsed_id = _parse_uuid_or_none(student_id)
    if parsed_id is None:
        return error("not_found", "Student not found.", 404)

    service = StudentService()
    try:
        student = service.get(parsed_id, institute_id=g.current_institute_id)
    except StudentServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_student(student))


@bp.patch("/<student_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def update_student(student_id: str):
    parsed_id = _parse_uuid_or_none(student_id)
    if parsed_id is None:
        return error("not_found", "Student not found.", 404)

    try:
        payload = UpdateStudentRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = StudentService()
    try:
        student = service.update(
            parsed_id,
            institute_id=g.current_institute_id,
            **payload.model_dump(exclude_none=True),
        )
    except StudentServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(serialize_student(student))


@bp.delete("/<student_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def delete_student(student_id: str):
    parsed_id = _parse_uuid_or_none(student_id)
    if parsed_id is None:
        return error("not_found", "Student not found.", 404)

    service = StudentService()
    try:
        service.delete(parsed_id, institute_id=g.current_institute_id)
    except StudentServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok({"message": "Student removed."})


@bp.post("/import")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def import_students():
    if "file" not in request.files:
        return error("missing_file", "No file was uploaded (expected field 'file').", 422)

    file = request.files["file"]
    if not file.filename:
        return error("missing_file", "No file was uploaded.", 422)
    if not file.filename.lower().endswith(".csv"):
        return error("invalid_file_type", "Only .csv files are supported.", 422)

    data = file.read(MAX_CSV_UPLOAD_BYTES + 1)
    if len(data) > MAX_CSV_UPLOAD_BYTES:
        return error("file_too_large", "CSV file exceeds the maximum allowed size.", 422)

    service = StudentService()
    try:
        result = service.import_csv(g.current_institute_id, raw_bytes=data)
    except StudentServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(result)
