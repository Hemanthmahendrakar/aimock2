import uuid
from typing import Optional

from app.extensions import db
from app.models import Evaluation


class EvaluationRepository:
    def get_by_interview_and_dimension(
        self, interview_id: uuid.UUID, dimension: str
    ) -> Optional[Evaluation]:
        return (
            db.session.query(Evaluation)
            .filter(Evaluation.interview_id == interview_id, Evaluation.dimension == dimension)
            .first()
        )

    def list_for_interview(self, interview_id: uuid.UUID) -> list[Evaluation]:
        return (
            db.session.query(Evaluation)
            .filter(Evaluation.interview_id == interview_id)
            .all()
        )

    def upsert(self, evaluation: Evaluation) -> Evaluation:
        """
        Save-or-replace by (interview_id, dimension) — evaluation only
        ever runs once per interview in normal operation, but this
        makes a manual re-run (e.g. after switching AI_PROVIDER) safe
        rather than hitting the unique constraint.
        """
        existing = self.get_by_interview_and_dimension(
            evaluation.interview_id, evaluation.dimension
        )
        if existing is not None:
            existing.score = evaluation.score
            existing.criteria_scores = evaluation.criteria_scores
            existing.evidence = evaluation.evidence
            existing.strengths = evaluation.strengths
            existing.weaknesses = evaluation.weaknesses
            existing.improvement_suggestions = evaluation.improvement_suggestions
            existing.evaluation_source = evaluation.evaluation_source
            db.session.add(existing)
            db.session.flush()
            return existing

        db.session.add(evaluation)
        db.session.flush()
        return evaluation
