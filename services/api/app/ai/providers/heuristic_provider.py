"""
Heuristic provider: deterministic, no network calls. This is what
AI_PROVIDER="none" (the default) uses, and what the test suite runs
against — every test in this codebase must be able to run without
network access, so this provider is not optional infrastructure, it's
load-bearing for CI.

Resume analysis reuses Phase 6's candidate_profile_builder verbatim
(no duplication). Question generation reuses the static bank, picking
around whatever's already been asked. Follow-ups use a small,
deterministic rule matching the spec's "restrained interviewer"
guidance: a short/vague answer gets probed further; a substantial one
moves on — never "Great answer!"-style filler.
"""
from app.ai.providers.base import AIProvider
from app.ai.types import (
    ResumeAnalysis,
    QuestionContext,
    FollowupContext,
    GeneratedQuestion,
    RoundEvaluationContext,
    CommunicationEvaluationContext,
    EvaluationResult,
    ReportContext,
    ReportContent,
)
from app.services.candidate_profile_builder import build_candidate_profile
from app.services.interview_question_bank import pick_question
from app.services.heuristic_evaluator import (
    evaluate_round_heuristically,
    evaluate_communication_heuristically,
)
from app.services.heuristic_report import generate_report_heuristically

# Restrained, non-effusive probes — cycled, never the same phrase
# twice in a row within one round, matching the spec's explicit
# "do not repeatedly say 'Great answer!'" instruction.
_SHORT_ANSWER_PROBES = [
    "Can you explain that further?",
    "What do you mean by that, specifically?",
    "Let's approach that from another angle — can you give a concrete example?",
]

_SHORT_ANSWER_WORD_THRESHOLD = 12


class HeuristicProvider(AIProvider):
    def analyze_resume(self, resume_text: str) -> ResumeAnalysis:
        data = build_candidate_profile(resume_text)
        return ResumeAnalysis(**data, extraction_method="heuristic_v1")

    def generate_question(self, context: QuestionContext) -> GeneratedQuestion:
        text, topic = pick_question(
            context.round_type,
            topics=context.question_categories,
            exclude=context.previous_questions,
            candidate_profile=context.candidate_profile,
            question_index=len(context.previous_questions),
        )
        return GeneratedQuestion(question_text=text, source="heuristic_v1", topic=topic)

    def generate_followup(self, context: FollowupContext) -> GeneratedQuestion | None:
        word_count = len(context.answer_text.split())
        if word_count >= _SHORT_ANSWER_WORD_THRESHOLD:
            return None  # substantial answer — move on, no follow-up

        probe = _SHORT_ANSWER_PROBES[
            context.followups_asked_so_far % len(_SHORT_ANSWER_PROBES)
        ]
        return GeneratedQuestion(question_text=probe, source="heuristic_v1")

    def evaluate_answer(self, context: RoundEvaluationContext) -> EvaluationResult:
        return evaluate_round_heuristically(context)

    def evaluate_communication(
        self, context: CommunicationEvaluationContext
    ) -> EvaluationResult:
        return evaluate_communication_heuristically(context)

    def generate_report(self, context: ReportContext) -> ReportContent:
        return generate_report_heuristically(context)
