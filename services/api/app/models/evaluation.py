"""
Evaluation — structured, rubric-based scoring for one dimension of a
completed interview. Four dimensions per interview: technical,
managerial, hr (each scored from that round's Q&A) and communication
(scored across every answer in the interview, not round-specific —
how someone communicates isn't confined to one round).

Deliberately NOT a single "overall evaluation" blob — the spec is
explicit that evaluation must be structured per rubric, not generated
from one generic prompt. Four rows, four independent AI Gateway calls
(app/tasks/evaluation_tasks.py), so a failure grading one dimension
doesn't block the others.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationDimension:
    TECHNICAL = "technical"
    MANAGERIAL = "managerial"
    HR = "hr"
    COMMUNICATION = "communication"

    ALL = (TECHNICAL, MANAGERIAL, HR, COMMUNICATION)


class Evaluation(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "evaluations"

    interview_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False
    )
    dimension = db.Column(db.String(16), nullable=False)

    # 0-100, matching the spec's own report example ("Technical: 76").
    score = db.Column(db.Integer, nullable=False)

    # Per-rubric-criterion sub-scores, e.g. {"correctness": 80,
    # "technical_depth": 70, ...} — keys vary by dimension, each set
    # matching the exact criteria list in the spec's EVALUATION section.
    criteria_scores = db.Column(db.JSON, nullable=False, default=dict)

    # Short, specific quotes/observations grounding the score — never
    # a personality judgment, per the spec's explicit instruction.
    evidence = db.Column(db.JSON, nullable=False, default=list)
    strengths = db.Column(db.JSON, nullable=False, default=list)
    weaknesses = db.Column(db.JSON, nullable=False, default=list)
    improvement_suggestions = db.Column(db.JSON, nullable=False, default=list)

    # "heuristic_v1" (structural/statistical, no real content judgment
    # for technical/managerial/hr — see HeuristicProvider) or "ai_v1".
    evaluation_source = db.Column(db.String(64), nullable=False, default="heuristic_v1")

    __table_args__ = (
        db.CheckConstraint(
            f"dimension IN {EvaluationDimension.ALL}", name="ck_evaluations_dimension_valid"
        ),
        db.CheckConstraint("score >= 0 AND score <= 100", name="ck_evaluations_score_range"),
        db.UniqueConstraint(
            "interview_id", "dimension", name="uq_evaluations_interview_dimension"
        ),
        db.Index("ix_evaluations_interview_id", "interview_id"),
    )

    def __repr__(self) -> str:
        return f"<Evaluation {self.interview_id} {self.dimension} {self.score}>"
