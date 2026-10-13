"""
Report serializer. One shape, shared between the institute-admin route
and the student's own-report route — nothing in a ReportVersion is
institute-internal (raw Evaluation rows, which do carry more granular
detail, stay admin-only via the existing evaluations endpoint).
"""
from app.models import Report, ReportVersion


def serialize_report_version(version: ReportVersion) -> dict:
    return {
        "version_number": version.version_number,
        "overall_score": version.overall_score,
        "technical_score": version.technical_score,
        "communication_score": version.communication_score,
        "managerial_score": version.managerial_score,
        "hr_score": version.hr_score,
        "problem_solving_score": version.problem_solving_score,
        "strengths": version.strengths,
        "weaknesses": version.weaknesses,
        "technical_skill_gaps": version.technical_skill_gaps,
        "communication_improvements": version.communication_improvements,
        "interview_highlights": version.interview_highlights,
        "recommended_preparation": version.recommended_preparation,
        "improvement_plan": version.improvement_plan,
        "model_version": version.model_version,
        "prompt_version": version.prompt_version,
        "evaluation_version": version.evaluation_version,
        "report_source": version.report_source,
        "generated_at": version.generated_at.isoformat() if version.generated_at else None,
    }


def serialize_report(report: Report) -> dict | None:
    if report.current_version is None:
        return None
    return serialize_report_version(report.current_version)
