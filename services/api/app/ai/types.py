"""
Data types shared between AI Gateway providers. Plain dataclasses, not
pydantic — these never cross an HTTP boundary directly (routes use
their own schemas), so there's no validation-on-parse need here.
"""
from dataclasses import dataclass, field


@dataclass
class ResumeAnalysis:
    """Mirrors CandidateProfile's fields exactly, plus a source tag."""

    education: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    programming_languages: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    internships: list[str] = field(default_factory=list)
    experience: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    extraction_method: str = "heuristic_v1"

    def as_profile_fields(self) -> dict:
        """Dict of just the CandidateProfile columns, excluding the tag."""
        return {
            "education": self.education,
            "skills": self.skills,
            "programming_languages": self.programming_languages,
            "technologies": self.technologies,
            "projects": self.projects,
            "internships": self.internships,
            "experience": self.experience,
            "certifications": self.certifications,
            "achievements": self.achievements,
        }


@dataclass
class QuestionContext:
    """
    Everything generate_question()/generate_followup() are allowed to
    consider, per the spec's QUESTION ENGINE section: resume/candidate
    profile, target role, experience level, round, skills, difficulty,
    previous questions/answers, time remaining. `candidate_profile` is
    a plain dict shaped like ResumeAnalysis.as_profile_fields() (or
    empty if the student has no analyzed resume yet — not fatal,
    questions just skip resume-specific personalization).
    """

    round_type: str
    difficulty: str
    target_role: str
    experience_level: str | None
    question_categories: list[str]
    instructions: str | None
    candidate_profile: dict
    previous_questions: list[str]
    previous_answers: list[str]
    seconds_remaining: int


@dataclass
class FollowupContext:
    round_type: str
    difficulty: str
    original_question: str
    answer_text: str
    instructions: str | None
    followups_asked_so_far: int


@dataclass
class GeneratedQuestion:
    question_text: str
    source: str  # e.g. "heuristic_v1" / "ai_v1" — matches CandidateProfile.extraction_method naming
    topic: str | None = None  # e.g. "dbms", "ownership" — see InterviewQuestion.topic


@dataclass
class AnsweredQuestion:
    """One Q&A pair, as evaluation contexts need it — trimmed to just
    what a rubric-based evaluator should look at."""

    question_text: str
    answer_text: str
    topic: str | None
    time_taken_seconds: int | None


@dataclass
class RoundEvaluationContext:
    """
    Everything evaluate_answer() may consider for one round (technical/
    managerial/hr). Criteria names come from round_competencies.py,
    matching the spec's EVALUATION section exactly per dimension —
    e.g. technical: correctness, technical_depth, fundamentals,
    problem_solving, practical_knowledge.
    """

    round_type: str
    difficulty: str
    target_role: str
    criteria_names: list[str]
    answers: list[AnsweredQuestion]
    instructions: str | None


@dataclass
class CommunicationEvaluationContext:
    """
    evaluate_communication() looks across every answer in the
    interview, not one round — how someone communicates isn't confined
    to a single round.
    """

    answers: list[AnsweredQuestion]


@dataclass
class EvaluationResult:
    dimension: str  # one of EvaluationDimension.ALL
    score: int  # 0-100
    criteria_scores: dict  # {criterion_name: 0-100, ...}
    evidence: list[str]
    strengths: list[str]
    weaknesses: list[str]
    improvement_suggestions: list[str]
    source: str  # "heuristic_v1" / "ai_v1"


@dataclass
class ReportContext:
    """
    Everything generate_report() may consider: the interview's four
    completed evaluations, plus enough interview context (role,
    difficulty, candidate name) to write a report that reads as
    specific to this candidate rather than generic filler.
    """

    target_role: str
    difficulty: str
    student_name: str
    technical_eval: "EvaluationResult"
    managerial_eval: "EvaluationResult"
    hr_eval: "EvaluationResult"
    communication_eval: "EvaluationResult"


@dataclass
class ReportContent:
    """
    Only the narrative sections — numeric scores are computed
    deterministically from the four Evaluation rows (see
    ReportService), not left to the AI Gateway to invent or re-derive.
    """

    strengths: list[str]
    weaknesses: list[str]
    technical_skill_gaps: list[str]
    communication_improvements: list[str]
    interview_highlights: list[str]
    recommended_preparation: list[str]
    improvement_plan: list[str]
    source: str  # "heuristic_v1" / "ai_v1"
    model_version: str | None = None
