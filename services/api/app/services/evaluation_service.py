"""
Evaluation orchestration. Runs from app/tasks/evaluation_tasks.py, not
directly from a request — evaluation happens after an interview
completes, not synchronously in the completing request.
"""
import uuid

from app.ai.gateway import AIGateway
from app.ai.types import AnsweredQuestion, RoundEvaluationContext, CommunicationEvaluationContext
from app.models import Evaluation, EvaluationDimension, Interview, InterviewRoundType
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.campaign_repository import CampaignRepository
from app.services.evaluation_rubrics import criteria_for_dimension
from app.services.audit_service import AuditService

_ROUND_DIMENSIONS = [
    InterviewRoundType.TECHNICAL,
    InterviewRoundType.MANAGERIAL,
    InterviewRoundType.HR,
]


class EvaluationService:
    def __init__(self):
        self.interviews = InterviewRepository()
        self.campaigns = CampaignRepository()
        self.evaluations = EvaluationRepository()
        self.audit = AuditService()

    def _answered_questions_for_round(self, round_) -> list[AnsweredQuestion]:
        result = []
        for q in sorted(round_.questions, key=lambda q: q.sequence_order):
            answer = self.interviews.get_answer_for_question(q.id)
            if answer is None:
                continue
            result.append(
                AnsweredQuestion(
                    question_text=q.question_text,
                    answer_text=answer.transcript_text,
                    topic=q.topic,
                    time_taken_seconds=answer.time_taken_seconds,
                )
            )
        return result

    def evaluate_interview(self, interview_id: uuid.UUID) -> Interview:
        interview = self.interviews.get_by_id_unscoped(interview_id)
        if interview is None:
            raise ValueError(f"Interview {interview_id} not found")

        gateway = AIGateway()
        campaign = self.campaigns.get_by_id(
            interview.campaign_id, institute_id=interview.institute_id
        )
        target_role = campaign.role if campaign else "the target role"
        difficulty = campaign.difficulty if campaign else "medium"

        all_answers: list[AnsweredQuestion] = []
        instructions_by_round = {
            InterviewRoundType.TECHNICAL: campaign.technical_instructions if campaign else None,
            InterviewRoundType.MANAGERIAL: campaign.managerial_instructions if campaign else None,
            InterviewRoundType.HR: campaign.hr_instructions if campaign else None,
        }

        for round_type in _ROUND_DIMENSIONS:
            round_ = self.interviews.get_round(interview.id, round_type)
            answers = self._answered_questions_for_round(round_) if round_ else []
            all_answers.extend(answers)

            context = RoundEvaluationContext(
                round_type=round_type,
                difficulty=difficulty,
                target_role=target_role,
                criteria_names=criteria_for_dimension(round_type),
                answers=answers,
                instructions=instructions_by_round[round_type],
            )
            result = gateway.evaluate_answer(context)
            self.evaluations.upsert(
                Evaluation(
                    interview_id=interview.id,
                    dimension=round_type,
                    score=result.score,
                    criteria_scores=result.criteria_scores,
                    evidence=result.evidence,
                    strengths=result.strengths,
                    weaknesses=result.weaknesses,
                    improvement_suggestions=result.improvement_suggestions,
                    evaluation_source=result.source,
                )
            )

        comm_context = CommunicationEvaluationContext(answers=all_answers)
        comm_result = gateway.evaluate_communication(comm_context)
        self.evaluations.upsert(
            Evaluation(
                interview_id=interview.id,
                dimension=EvaluationDimension.COMMUNICATION,
                score=comm_result.score,
                criteria_scores=comm_result.criteria_scores,
                evidence=comm_result.evidence,
                strengths=comm_result.strengths,
                weaknesses=comm_result.weaknesses,
                improvement_suggestions=comm_result.improvement_suggestions,
                evaluation_source=comm_result.source,
            )
        )

        return interview
