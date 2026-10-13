"""
Report generation orchestration. Runs from
app/tasks/report_tasks.py, after an interview's four evaluations
(Phase 10) are complete — never synchronously in a request.

Numeric scores are computed here, deterministically, from the
Evaluation rows already in the database — no AI call needed for
arithmetic, and no risk of a provider inventing a different score
than what's actually stored. Only the narrative sections go through
AIGateway.generate_report().
"""
import uuid
from datetime import datetime, timezone

from app.ai.gateway import AIGateway
from app.ai.types import ReportContext
from app.models import Report, ReportVersion, Interview, EvaluationDimension
from app.repositories.report_repository import ReportRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.student_repository import StudentRepository
from app.services.audit_service import AuditService


class ReportServiceError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class MissingEvaluations(ReportServiceError):
    def __init__(self, missing: list[str]):
        super().__init__(f"Missing evaluations for dimension(s): {', '.join(missing)}")


def _evaluation_version_tag(sources: list[str]) -> str:
    unique = set(sources)
    if len(unique) == 1:
        return unique.pop()
    return "mixed_v1"


class ReportService:
    def __init__(self):
        self.reports = ReportRepository()
        self.evaluations = EvaluationRepository()
        self.interviews = InterviewRepository()
        self.campaigns = CampaignRepository()
        self.students = StudentRepository()
        self.audit = AuditService()

    def generate_report(self, interview_id: uuid.UUID) -> Report:
        interview = self.interviews.get_by_id_unscoped(interview_id)
        if interview is None:
            raise ReportServiceError(f"Interview {interview_id} not found")

        evals_by_dim = {
            e.dimension: e for e in self.evaluations.list_for_interview(interview.id)
        }
        missing = [d for d in EvaluationDimension.ALL if d not in evals_by_dim]
        if missing:
            raise MissingEvaluations(missing)

        technical = evals_by_dim[EvaluationDimension.TECHNICAL]
        managerial = evals_by_dim[EvaluationDimension.MANAGERIAL]
        hr = evals_by_dim[EvaluationDimension.HR]
        communication = evals_by_dim[EvaluationDimension.COMMUNICATION]

        # Documented assumption (also noted on ReportVersion.overall_score):
        # unweighted mean of the four dimension scores. The spec's report
        # example is illustrative, not a specified formula.
        overall_score = round(
            (technical.score + managerial.score + hr.score + communication.score) / 4
        )
        problem_solving_score = technical.criteria_scores.get(
            "problem_solving", technical.score
        )

        campaign = self.campaigns.get_by_id(
            interview.campaign_id, institute_id=interview.institute_id
        )
        student = self.students.get_by_id(
            interview.student_id, institute_id=interview.institute_id
        )

        gateway = AIGateway()
        context = ReportContext(
            target_role=campaign.role if campaign else "the target role",
            difficulty=campaign.difficulty if campaign else "medium",
            student_name=student.name if student else "the candidate",
            technical_eval=technical,
            managerial_eval=managerial,
            hr_eval=hr,
            communication_eval=communication,
        )
        content = gateway.generate_report(context)

        report = self.reports.get_by_interview(interview.id)
        if report is None:
            report = Report(interview_id=interview.id, institute_id=interview.institute_id)
            self.reports.create(report)

        version_number = self.reports.next_version_number(report.id)
        version = ReportVersion(
            report_id=report.id,
            version_number=version_number,
            overall_score=overall_score,
            technical_score=technical.score,
            communication_score=communication.score,
            managerial_score=managerial.score,
            hr_score=hr.score,
            problem_solving_score=problem_solving_score,
            strengths=content.strengths,
            weaknesses=content.weaknesses,
            technical_skill_gaps=content.technical_skill_gaps,
            communication_improvements=content.communication_improvements,
            interview_highlights=content.interview_highlights,
            recommended_preparation=content.recommended_preparation,
            improvement_plan=content.improvement_plan,
            model_version=content.model_version,
            evaluation_version=_evaluation_version_tag(
                [technical.source, managerial.source, hr.source, communication.source]
            ),
            report_source=content.source,
            generated_at=datetime.now(timezone.utc),
        )
        self.reports.create_version(version)

        report.current_version_id = version.id
        self.reports.save(report)

        self.audit.log(
            event_type="report.generated",
            institute_id=interview.institute_id,
            metadata={
                "interview_id": str(interview.id), "report_id": str(report.id),
                "version_number": version_number, "source": content.source,
            },
        )
        return report
