"""
Resume-specific serializers, kept in their own module since they're
sizable enough to clutter the shared serializers.py.
"""
from app.models import ResumeVersion, CandidateProfile
from app.services.file_storage_service import FileStorageService, FileStorageError


def serialize_candidate_profile(profile: CandidateProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "id": str(profile.id),
        "education": profile.education,
        "skills": profile.skills,
        "programming_languages": profile.programming_languages,
        "technologies": profile.technologies,
        "projects": profile.projects,
        "internships": profile.internships,
        "experience": profile.experience,
        "certifications": profile.certifications,
        "achievements": profile.achievements,
        "extraction_method": profile.extraction_method,
        "analysis_status": profile.analysis_status,
        "analysis_error": profile.analysis_error,
    }


def serialize_resume_version(version: ResumeVersion, *, include_profile: bool = True) -> dict:
    # Bucket stays private (same pattern as institute logos in Phase 2)
    # — sign a short-lived download URL at read time rather than
    # exposing a permanent/public link.
    try:
        file_url = FileStorageService().get_signed_url(version.s3_key)
    except FileStorageError:
        file_url = None

    result = {
        "id": str(version.id),
        "resume_id": str(version.resume_id),
        "version_number": version.version_number,
        "original_filename": version.original_filename,
        "file_size_bytes": version.file_size_bytes,
        "content_type": version.content_type,
        "file_url": file_url,
        "extraction_status": version.extraction_status,
        "extraction_error": version.extraction_error,
        "extracted_text": version.extracted_text,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
    if include_profile:
        result["candidate_profile"] = serialize_candidate_profile(version.candidate_profile)
    return result
