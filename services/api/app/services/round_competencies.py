"""
Default subject areas (technical) / competencies (managerial, HR) per
round, straight from the spec's TECHNICAL/MANAGERIAL/HR ROUND
sections. Used only as a fallback — when a campaign carries its own
categories (technical) or evaluation-criteria keys (managerial/HR,
copied from an InterviewTemplateRound — see Phase 5), those take
precedence. See topics_for_round().
"""
from app.models import Campaign
from app.models.interview_template import InterviewRoundType

DEFAULT_TECHNICAL_TOPICS = [
    "dsa",
    "algorithms",
    "oop",
    "dbms",
    "operating_systems",
    "computer_networks",
]

DEFAULT_MANAGERIAL_COMPETENCIES = [
    "decision_making",
    "ownership",
    "teamwork",
    "conflict_handling",
    "leadership",
    "problem_solving",
    "prioritization",
    "project_understanding",
]

DEFAULT_HR_COMPETENCIES = [
    "professional_communication",
    "self_awareness",
    "motivation",
    "career_goals",
    "strengths_weaknesses",
    "professional_behavior",
    "role_alignment",
]


def topics_for_round(round_type: str, campaign: "Campaign | None") -> list[str]:
    """
    Returns the ordered list of topics/competencies a round's questions
    should draw from. Campaign-specific config wins when present;
    otherwise falls back to the spec's default list for that round.
    """
    if round_type == InterviewRoundType.TECHNICAL:
        if campaign and campaign.question_categories:
            return list(campaign.question_categories)
        return list(DEFAULT_TECHNICAL_TOPICS)

    if round_type == InterviewRoundType.MANAGERIAL:
        criteria = (campaign.evaluation_criteria or {}).get("managerial", {}) if campaign else {}
        if criteria:
            return list(criteria.keys())
        return list(DEFAULT_MANAGERIAL_COMPETENCIES)

    if round_type == InterviewRoundType.HR:
        criteria = (campaign.evaluation_criteria or {}).get("hr", {}) if campaign else {}
        if criteria:
            return list(criteria.keys())
        return list(DEFAULT_HR_COMPETENCIES)

    return []
