import uuid
from typing import Optional

from app.extensions import db
from app.models import Resume, ResumeVersion, CandidateProfile


class ResumeRepository:
    def get_by_student(
        self, student_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> Optional[Resume]:
        return (
            db.session.query(Resume)
            .filter(Resume.student_id == student_id, Resume.institute_id == institute_id)
            .first()
        )

    def create(self, resume: Resume) -> Resume:
        db.session.add(resume)
        db.session.flush()
        return resume

    def save(self, resume: Resume) -> Resume:
        db.session.add(resume)
        db.session.flush()
        return resume

    def next_version_number(self, resume_id: uuid.UUID) -> int:
        current_max = (
            db.session.query(db.func.max(ResumeVersion.version_number))
            .filter(ResumeVersion.resume_id == resume_id)
            .scalar()
        )
        return (current_max or 0) + 1

    def create_version(self, version: ResumeVersion) -> ResumeVersion:
        db.session.add(version)
        db.session.flush()
        return version

    def get_version_by_id(self, version_id: uuid.UUID) -> Optional[ResumeVersion]:
        return db.session.get(ResumeVersion, version_id)

    def get_version_scoped(
        self, version_id: uuid.UUID, *, institute_id: uuid.UUID, resume_id: uuid.UUID
    ) -> Optional[ResumeVersion]:
        return (
            db.session.query(ResumeVersion)
            .filter(
                ResumeVersion.id == version_id,
                ResumeVersion.institute_id == institute_id,
                ResumeVersion.resume_id == resume_id,
            )
            .first()
        )

    def list_versions(
        self, resume_id: uuid.UUID, *, page: int, per_page: int
    ) -> tuple[list[ResumeVersion], int]:
        query = db.session.query(ResumeVersion).filter(ResumeVersion.resume_id == resume_id)
        total = query.count()
        items = (
            query.order_by(ResumeVersion.version_number.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    # ------------------------------------------------------------------
    def get_profile_by_version(self, version_id: uuid.UUID) -> Optional[CandidateProfile]:
        return (
            db.session.query(CandidateProfile)
            .filter(CandidateProfile.resume_version_id == version_id)
            .first()
        )

    def get_current_profile_for_student(
        self, student_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> Optional[CandidateProfile]:
        """
        Used by the interview engine to personalize question generation.
        Returns None if the student has no resume, no current version,
        or that version hasn't finished analysis yet — all non-fatal:
        question generation just skips resume-specific personalization.
        """
        resume = self.get_by_student(student_id, institute_id=institute_id)
        if resume is None or resume.current_version_id is None:
            return None
        return self.get_profile_by_version(resume.current_version_id)

    def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        db.session.add(profile)
        db.session.flush()
        return profile
