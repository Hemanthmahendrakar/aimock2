"""
Resume pipeline: Resume (one per student, the "current" pointer) ->
ResumeVersion (one row per upload, append-only) -> CandidateProfile
(structured extraction result, one per version since content differs
across versions).

institute_id lives on both Resume and ResumeVersion for the same
reason it's on Campaign/Student — direct tenant-scoped queries without
a join back through Student on every lookup.
"""
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ProcessingStatus:
    """Shared status shape for both text extraction and candidate-
    profile analysis — same lifecycle, so one enum for both."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    ALL = (PENDING, PROCESSING, COMPLETED, FAILED)


class Resume(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "resumes"

    institute_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False
    )
    student_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    # Set once the first version finishes uploading. Nullable only for
    # the brief window between creating the Resume row and creating its
    # first ResumeVersion — see ResumeService.upload.
    current_version_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("resume_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    versions = db.relationship(
        "ResumeVersion",
        foreign_keys="ResumeVersion.resume_id",
        backref="resume",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("student_id", name="uq_resumes_student_id"),
        db.Index("ix_resumes_institute_id", "institute_id"),
    )

    def __repr__(self) -> str:
        return f"<Resume {self.id} student={self.student_id}>"


class ResumeVersion(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "resume_versions"

    resume_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    institute_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False
    )

    version_number = db.Column(db.Integer, nullable=False)

    original_filename = db.Column(db.String(255), nullable=False)
    s3_key = db.Column(db.String(1024), nullable=False)
    file_size_bytes = db.Column(db.Integer, nullable=False)
    content_type = db.Column(db.String(128), nullable=False)

    extraction_status = db.Column(db.String(16), nullable=False, default=ProcessingStatus.PENDING)
    extracted_text = db.Column(db.Text, nullable=True)
    extraction_error = db.Column(db.Text, nullable=True)

    candidate_profile = db.relationship(
        "CandidateProfile", backref="resume_version", uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "resume_id", "version_number", name="uq_resume_versions_resume_version"
        ),
        db.CheckConstraint(
            f"extraction_status IN {ProcessingStatus.ALL}",
            name="ck_resume_versions_extraction_status_valid",
        ),
        db.Index("ix_resume_versions_resume_id", "resume_id"),
        db.Index("ix_resume_versions_institute_id", "institute_id"),
    )

    def __repr__(self) -> str:
        return f"<ResumeVersion {self.id} v{self.version_number}>"


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "candidate_profiles"

    resume_version_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Each a JSON list of strings. Schema-flexible on purpose — the
    # exact shape these take will change once Phase 8 swaps the
    # heuristic builder for a real AI Gateway call.
    education = db.Column(db.JSON, nullable=False, default=list)
    skills = db.Column(db.JSON, nullable=False, default=list)
    programming_languages = db.Column(db.JSON, nullable=False, default=list)
    technologies = db.Column(db.JSON, nullable=False, default=list)
    projects = db.Column(db.JSON, nullable=False, default=list)
    internships = db.Column(db.JSON, nullable=False, default=list)
    experience = db.Column(db.JSON, nullable=False, default=list)
    certifications = db.Column(db.JSON, nullable=False, default=list)
    achievements = db.Column(db.JSON, nullable=False, default=list)

    # e.g. "heuristic_v1" now, "ai_v1" from Phase 8 onward — lets a
    # report later explain which method produced a given profile,
    # mirroring the model/prompt versioning the spec asks for on
    # evaluation reports.
    extraction_method = db.Column(db.String(64), nullable=True)

    analysis_status = db.Column(db.String(16), nullable=False, default=ProcessingStatus.PENDING)
    analysis_error = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "resume_version_id", name="uq_candidate_profiles_resume_version_id"
        ),
        db.CheckConstraint(
            f"analysis_status IN {ProcessingStatus.ALL}",
            name="ck_candidate_profiles_analysis_status_valid",
        ),
    )

    def __repr__(self) -> str:
        return f"<CandidateProfile {self.id} version={self.resume_version_id}>"
