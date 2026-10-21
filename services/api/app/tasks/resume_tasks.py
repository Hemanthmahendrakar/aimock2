"""
Background processing for uploaded resumes. Two sequential steps, each
with its own status/error tracking so a failure in one is visible
without hiding whether the other succeeded:
  1. Text extraction (deterministic, resume_extraction_service)
  2. Candidate profile building, via the AI Gateway (Phase 8) — heuristic
     by default, real AI when AI_PROVIDER is configured. Either way the
     resulting extraction_method tag says which one actually ran.
"""
import logging
import uuid

from app.extensions import celery, db
from app.models import ResumeVersion, CandidateProfile, ProcessingStatus
from app.repositories.resume_repository import ResumeRepository
from app.ai.gateway import AIGateway
from app.services.file_storage_service import FileStorageService, FileStorageError
from app.services.resume_extraction_service import extract_text, ExtractionFailed, UnsupportedContentType

logger = logging.getLogger("app.tasks.resume")


@celery.task(name="resume.process_version", bind=True, max_retries=2)
def process_resume_version(self, resume_version_id: str) -> None:
    repo = ResumeRepository()
    version = repo.get_version_by_id(uuid.UUID(resume_version_id))
    if version is None:
        logger.warning("process_resume_version: version %s not found", resume_version_id)
        return

    version.extraction_status = ProcessingStatus.PROCESSING
    db.session.commit()

    try:
        raw_bytes = FileStorageService().download_bytes(version.s3_key)
        text = extract_text(content_type=version.content_type, data=raw_bytes)
    except (FileStorageError, ExtractionFailed, UnsupportedContentType) as exc:
        version.extraction_status = ProcessingStatus.FAILED
        version.extraction_error = str(exc)[:2000]
        db.session.commit()
        return
    except Exception as exc:  # noqa: BLE001 — last-resort guard for a background job
        logger.exception("Unexpected error extracting resume text")
        version.extraction_status = ProcessingStatus.FAILED
        version.extraction_error = f"Unexpected error: {exc}"[:2000]
        db.session.commit()
        return

    version.extracted_text = text
    version.extraction_status = ProcessingStatus.COMPLETED
    version.extraction_error = None
    db.session.commit()

    _build_and_save_profile(repo, version, text)


def _build_and_save_profile(repo: ResumeRepository, version: ResumeVersion, text: str) -> None:
    profile = repo.get_profile_by_version(version.id)
    if profile is None:
        profile = CandidateProfile(resume_version_id=version.id)

    try:
        analysis = AIGateway().analyze_resume(text)
        for key, value in analysis.as_profile_fields().items():
            setattr(profile, key, value)
        profile.extraction_method = analysis.extraction_method
        profile.analysis_status = ProcessingStatus.COMPLETED
        profile.analysis_error = None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error building candidate profile")
        profile.analysis_status = ProcessingStatus.FAILED
        profile.analysis_error = f"Unexpected error: {exc}"[:2000]

    repo.save_profile(profile)
    db.session.commit()
