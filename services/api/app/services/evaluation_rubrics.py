"""
Rubric criteria per evaluation dimension, straight from the spec's
EVALUATION section. Deliberately a separate list from
round_competencies.py's topics — those are "what to ask about"
(e.g. managerial: ownership, conflict_handling, prioritization...);
these are "what to grade on" (e.g. managerial: decision_making,
ownership, teamwork, leadership, situational_reasoning — a narrower,
different set per the spec). Conflating the two would silently drift
from the spec's exact rubric the moment either list changes.
"""
from app.models import EvaluationDimension

TECHNICAL_CRITERIA = [
    "correctness",
    "technical_depth",
    "fundamentals",
    "problem_solving",
    "practical_knowledge",
]

MANAGERIAL_CRITERIA = [
    "decision_making",
    "ownership",
    "teamwork",
    "leadership",
    "situational_reasoning",
]

HR_CRITERIA = [
    "relevance",
    "self_awareness",
    "professionalism",
    "motivation",
]

COMMUNICATION_CRITERIA = [
    "clarity",
    "structure",
    "conciseness",
    "fluency",
    "pace",
    "filler_words",
    "repetition",
    "relevance",
]

_CRITERIA_BY_DIMENSION = {
    EvaluationDimension.TECHNICAL: TECHNICAL_CRITERIA,
    EvaluationDimension.MANAGERIAL: MANAGERIAL_CRITERIA,
    EvaluationDimension.HR: HR_CRITERIA,
    EvaluationDimension.COMMUNICATION: COMMUNICATION_CRITERIA,
}


def criteria_for_dimension(dimension: str) -> list[str]:
    return list(_CRITERIA_BY_DIMENSION.get(dimension, []))
