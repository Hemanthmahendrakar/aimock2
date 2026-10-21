"""
Business logic for resume upload and retrieval. Every method takes an
institute_id that MUST already be g.current_institute_id, and every
student_id is checked against StudentRepository (scoped by that same
institute_id) before anything resume-related happens — so a resume
can never be uploaded to, or read from, a student outside the caller's
institute.
"""
import uuid

from app.extensions import db
from app.models import Resume, ResumeVersion, ProcessingStatus
from app.repositories.resume_repository import ResumeRepository
from app.repositories.student_repository import StudentRepository
from app.services.audit_service import AuditService
from app.services.file_storage_service import FileStorageService, FileStorageError
from app.utils.file_validation import validate_upload, FileValidationError


class ResumeServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class StudentNotFoundForResume(ResumeServiceError):
    def __init__(self):
        super().__init__("student_not_found", "Student not found.", 404)


class ResumeNotFound(ResumeServiceError):
    def __init__(self):
        super().__init__("resume_not_found", "This student has no resume on file.", 404)


class ResumeVersionNotFound(ResumeServiceError):
    def __init__(self):
        super().__init__("resume_version_not_found", "Resume version not found.", 404)


class ResumeService:
    def __init__(self):
        self.resumes = ResumeRepository()
        self.students = StudentRepository()
        self.audit = AuditService()

    def _get_student_or_404(self, student_id: uuid.UUID, *, institute_id: uuid.UUID):
        student = self.students.get_by_id(student_id, institute_id=institute_id)
        if student is None:
            raise StudentNotFoundForResume()
        return student

    # ------------------------------------------------------------------
    def upload(
        self,
        *,
        institute_id: uuid.UUID,
        student_id: uuid.UUID,
        filename: str,
        data: bytes,
    ) -> ResumeVersion:
        from flask import current_app

        self._get_student_or_404(student_id, institute_id=institute_id)

        try:
            content_type = validate_upload(
                data=data,
                max_size_bytes=current_app.config["RESUME_MAX_SIZE_BYTES"],
                allowed_content_types=current_app.config["RESUME_ALLOWED_CONTENT_TYPES"],
            )
        except FileValidationError as exc:
            raise ResumeServiceError("invalid_file", str(exc), 422) from exc

        resume = self.resumes.get_by_student(student_id, institute_id=institute_id)
        if resume is None:
            resume = Resume(institute_id=institute_id, student_id=student_id)
            self.resumes.create(resume)

        storage = FileStorageService()
        object_key = storage.build_object_key(
            prefix=f"institutes/{institute_id}/students/{student_id}/resumes",
            filename=filename,
        )
        try:
            storage.upload_bytes(key=object_key, data=data, content_type=content_type)
        except FileStorageError as exc:
            raise ResumeServiceError("storage_error", str(exc), 502) from exc

        version_number = self.resumes.next_version_number(resume.id)
        version = ResumeVersion(
            resume_id=resume.id,
            institute_id=institute_id,
            version_number=version_number,
            original_filename=filename,
            s3_key=object_key,
            file_size_bytes=len(data),
            content_type=content_type,
            extraction_status=ProcessingStatus.PENDING,
        )
        self.resumes.create_version(version)

        resume.current_version_id = version.id
        self.resumes.save(resume)

        self.audit.log(
            event_type="resume.uploaded",
            institute_id=institute_id,
            metadata={
                "student_id": str(student_id),
                "resume_version_id": str(version.id),
                "version_number": version_number,
            },
        )
        db.session.commit()

        # Import here, not at module load, so a broken Celery config
        # can't break unrelated routes that import ResumeService.
        from app.tasks.resume_tasks import process_resume_version

        process_resume_version.delay(str(version.id))

        return version

    def get_current(self, student_id: uuid.UUID, *, institute_id: uuid.UUID) -> ResumeVersion:
        self._get_student_or_404(student_id, institute_id=institute_id)
        resume = self.resumes.get_by_student(student_id, institute_id=institute_id)
        if resume is None or resume.current_version_id is None:
            raise ResumeNotFound()
        version = self.resumes.get_version_by_id(resume.current_version_id)
        if version is None:
            raise ResumeNotFound()
        return version

    def list_versions(
        self, student_id: uuid.UUID, *, institute_id: uuid.UUID, page: int, per_page: int
    ) -> tuple[list[ResumeVersion], int]:
        self._get_student_or_404(student_id, institute_id=institute_id)
        resume = self.resumes.get_by_student(student_id, institute_id=institute_id)
        if resume is None:
            return [], 0
        page = max(page, 1)
        per_page = min(max(per_page, 1), 100)
        return self.resumes.list_versions(resume.id, page=page, per_page=per_page)

    def get_version(
        self, student_id: uuid.UUID, version_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> ResumeVersion:
        self._get_student_or_404(student_id, institute_id=institute_id)
        resume = self.resumes.get_by_student(student_id, institute_id=institute_id)
        if resume is None:
            raise ResumeVersionNotFound()
        version = self.resumes.get_version_scoped(
            version_id, institute_id=institute_id, resume_id=resume.id
        )
        if version is None:
            raise ResumeVersionNotFound()
        return version
