"""
Business logic for student management. Like InstituteService, every
method takes an institute_id that MUST already be g.current_institute_id
— derived from the authenticated session, never from client input.
"""
import csv
import io
import uuid
from typing import Optional

from app.extensions import db
from app.models import Student, StudentStatus
from app.repositories.student_repository import StudentRepository
from app.services.audit_service import AuditService

MAX_IMPORT_ROWS = 5000
MAX_IMPORT_FILE_BYTES = 5 * 1024 * 1024

REQUIRED_IMPORT_COLUMNS = {"name", "email"}
OPTIONAL_IMPORT_COLUMNS = {"roll_number", "department", "batch", "phone"}
ALL_IMPORT_COLUMNS = REQUIRED_IMPORT_COLUMNS | OPTIONAL_IMPORT_COLUMNS


class StudentServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class StudentNotFound(StudentServiceError):
    def __init__(self):
        super().__init__("student_not_found", "Student not found.", 404)


class DuplicateStudent(StudentServiceError):
    def __init__(self, field: str):
        super().__init__(
            "duplicate_student", f"A student with this {field} already exists.", 409
        )


class StudentService:
    def __init__(self):
        self.students = StudentRepository()
        self.audit = AuditService()

    # ------------------------------------------------------------------
    def create(
        self,
        institute_id: uuid.UUID,
        *,
        name: str,
        email: str,
        roll_number: Optional[str] = None,
        department: Optional[str] = None,
        batch: Optional[str] = None,
        phone: Optional[str] = None,
        campus_id: Optional[str] = None,
        course: Optional[str] = None,
        graduation_year: Optional[int] = None,
        experience_level: Optional[str] = None,
    ) -> Student:
        if self.students.get_by_email(email, institute_id=institute_id):
            raise DuplicateStudent("email")
        if roll_number and self.students.get_by_roll_number(
            roll_number, institute_id=institute_id
        ):
            raise DuplicateStudent("roll number")

        campus_uuid = None
        if campus_id:
            try: campus_uuid = uuid.UUID(str(campus_id))
            except (ValueError, TypeError): raise StudentServiceError("invalid_campus_id", "Invalid campus_id.", 422)
            from app.models import Campus
            if Campus.query.filter_by(id=campus_uuid, institute_id=institute_id, deleted_at=None).first() is None:
                raise StudentServiceError("campus_not_found", "Campus not found.", 404)

        student = Student(
            institute_id=institute_id,
            name=name,
            email=email,
            roll_number=roll_number,
            department=department,
            batch=batch,
            phone=phone,
            campus_id=campus_uuid,
            course=course,
            graduation_year=graduation_year,
            experience_level=experience_level,
        )
        self.students.create(student)
        self.audit.log(
            event_type="student.created", institute_id=institute_id,
            metadata={"student_id": str(student.id)},
        )
        db.session.commit()
        return student

    def get(self, student_id: uuid.UUID, *, institute_id: uuid.UUID) -> Student:
        student = self.students.get_by_id(student_id, institute_id=institute_id)
        if student is None:
            raise StudentNotFound()
        return student

    def list(
        self,
        *,
        institute_id: uuid.UUID,
        page: int,
        per_page: int,
        search: Optional[str] = None,
        department: Optional[str] = None,
        batch: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[Student], int]:
        page = max(page, 1)
        per_page = min(max(per_page, 1), 100)
        return self.students.list_paginated(
            institute_id=institute_id,
            page=page,
            per_page=per_page,
            search=search,
            department=department,
            batch=batch,
            status=status,
        )

    def update(self, student_id: uuid.UUID, *, institute_id: uuid.UUID, **fields) -> Student:
        student = self.get(student_id, institute_id=institute_id)

        new_email = fields.get("email")
        if new_email and new_email.lower() != student.email.lower():
            existing = self.students.get_by_email(new_email, institute_id=institute_id)
            if existing and existing.id != student.id:
                raise DuplicateStudent("email")

        new_roll = fields.get("roll_number")
        if new_roll and new_roll != student.roll_number:
            existing = self.students.get_by_roll_number(new_roll, institute_id=institute_id)
            if existing and existing.id != student.id:
                raise DuplicateStudent("roll number")

        if fields.get("status") is not None and fields["status"] not in StudentStatus.ALL:
            raise StudentServiceError("invalid_status", "Invalid student status.", 422)

        if fields.get("campus_id") is not None:
            try: campus_uuid = uuid.UUID(str(fields["campus_id"]))
            except (ValueError, TypeError): raise StudentServiceError("invalid_campus_id", "Invalid campus_id.", 422)
            from app.models import Campus
            if Campus.query.filter_by(id=campus_uuid, institute_id=institute_id, deleted_at=None).first() is None:
                raise StudentServiceError("campus_not_found", "Campus not found.", 404)
            fields["campus_id"] = campus_uuid

        for key in ("name", "email", "roll_number", "department", "batch", "phone", "status", "course", "graduation_year", "experience_level", "campus_id"):
            value = fields.get(key)
            if value is not None:
                setattr(student, key, value)

        self.students.save(student)
        self.audit.log(
            event_type="student.updated", institute_id=institute_id,
            metadata={"student_id": str(student.id), "fields": list(fields.keys())},
        )
        db.session.commit()
        return student

    def delete(self, student_id: uuid.UUID, *, institute_id: uuid.UUID) -> None:
        student = self.get(student_id, institute_id=institute_id)
        student.soft_delete()
        self.students.save(student)
        self.audit.log(
            event_type="student.deleted", institute_id=institute_id,
            metadata={"student_id": str(student.id)},
        )
        db.session.commit()

    # ------------------------------------------------------------------
    # CSV import
    # ------------------------------------------------------------------
    def import_csv(self, institute_id: uuid.UUID, *, raw_bytes: bytes) -> dict:
        if len(raw_bytes) > MAX_IMPORT_FILE_BYTES:
            raise StudentServiceError(
                "file_too_large",
                f"CSV file exceeds the maximum size of "
                f"{MAX_IMPORT_FILE_BYTES // (1024 * 1024)}MB.",
                422,
            )

        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise StudentServiceError(
                "invalid_encoding", "CSV file must be UTF-8 encoded.", 422
            ) from exc

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise StudentServiceError("empty_file", "CSV file has no header row.", 422)

        header = {h.strip().lower() for h in reader.fieldnames}
        missing = REQUIRED_IMPORT_COLUMNS - header
        if missing:
            raise StudentServiceError(
                "missing_columns",
                f"CSV is missing required column(s): {', '.join(sorted(missing))}.",
                422,
            )

        rows = list(reader)
        if len(rows) > MAX_IMPORT_ROWS:
            raise StudentServiceError(
                "too_many_rows",
                f"CSV has more than the maximum of {MAX_IMPORT_ROWS} rows.",
                422,
            )

        # Track emails/roll_numbers seen within this file so duplicates
        # inside the same upload are caught too, not just against the DB.
        seen_emails: set[str] = set()
        seen_rolls: set[str] = set()

        created = 0
        errors: list[dict] = []
        to_create: list[Student] = []

        for i, row in enumerate(rows, start=2):  # start=2: row 1 is the header
            normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            name = normalized.get("name", "")
            email = normalized.get("email", "")

            if not name or not email:
                errors.append({"row": i, "message": "Missing required name or email."})
                continue

            email_lower = email.lower()
            roll_number = normalized.get("roll_number") or None

            if email_lower in seen_emails:
                errors.append({"row": i, "message": f"Duplicate email in file: {email}"})
                continue
            if roll_number and roll_number in seen_rolls:
                errors.append(
                    {"row": i, "message": f"Duplicate roll number in file: {roll_number}"}
                )
                continue
            if self.students.get_by_email(email, institute_id=institute_id):
                errors.append({"row": i, "message": f"Email already exists: {email}"})
                continue
            if roll_number and self.students.get_by_roll_number(
                roll_number, institute_id=institute_id
            ):
                errors.append(
                    {"row": i, "message": f"Roll number already exists: {roll_number}"}
                )
                continue

            seen_emails.add(email_lower)
            if roll_number:
                seen_rolls.add(roll_number)

            to_create.append(
                Student(
                    institute_id=institute_id,
                    name=name,
                    email=email,
                    roll_number=roll_number,
                    department=normalized.get("department") or None,
                    batch=normalized.get("batch") or None,
                    phone=normalized.get("phone") or None,
                )
            )

        if to_create:
            self.students.bulk_create(to_create)
            created = len(to_create)

        self.audit.log(
            event_type="student.imported",
            institute_id=institute_id,
            metadata={"created": created, "errors": len(errors), "total_rows": len(rows)},
        )
        db.session.commit()

        return {
            "total_rows": len(rows),
            "created": created,
            "skipped": len(errors),
            "errors": errors[:200],  # cap response size; audit log has the full count
        }
