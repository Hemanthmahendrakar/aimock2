"""
Deterministic report synthesis backing HeuristicProvider. Unlike
evaluate_round_heuristically (which is honest about NOT judging
content), this function has real material to work with — it's
aggregating four already-computed EvaluationResult objects (each with
their own evidence/strengths/weaknesses/suggestions), not inventing
new judgments from raw text. Combining and organizing that material
into report sections is legitimate synthesis work, whether or not a
real AI model does it.
"""
from app.ai.types import ReportContext, ReportContent

_MAX_ITEMS_PER_SECTION = 5


def _dedupe_capped(items: list[str], cap: int = _MAX_ITEMS_PER_SECTION) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
        if len(result) >= cap:
            break
    return result


def generate_report_heuristically(context: ReportContext) -> ReportContent:
    evals = [
        context.technical_eval,
        context.managerial_eval,
        context.hr_eval,
        context.communication_eval,
    ]

    strengths = _dedupe_capped([s for e in evals for s in e.strengths])
    weaknesses = _dedupe_capped([w for e in evals for w in e.weaknesses])

    technical_skill_gaps = _dedupe_capped(
        context.technical_eval.weaknesses or context.technical_eval.improvement_suggestions
    )

    communication_improvements = _dedupe_capped(
        context.communication_eval.weaknesses
        or context.communication_eval.improvement_suggestions
    )

    # A handful of the most specific evidence lines across every
    # dimension — these read as concrete moments from the interview
    # rather than generic commentary, matching the spec's "interview
    # highlights" field.
    interview_highlights = _dedupe_capped(
        [ev for e in evals for ev in e.evidence], cap=_MAX_ITEMS_PER_SECTION
    )

    recommended_preparation = _dedupe_capped(
        context.technical_eval.improvement_suggestions
        + context.managerial_eval.improvement_suggestions
        + context.hr_eval.improvement_suggestions
    )

    # Ordered, actionable next steps — reuses the same underlying
    # material as recommended_preparation/communication_improvements
    # but framed as a plan rather than a flat list, matching the
    # spec's report example ("Revise X", "Practice Y", "Practice Z").
    improvement_plan = _dedupe_capped(
        technical_skill_gaps[:2] + communication_improvements[:1] + recommended_preparation[:2]
    )
    if not improvement_plan:
        improvement_plan = ["Continue practicing mock interviews to build consistency."]

    return ReportContent(
        strengths=strengths or ["No standout strengths were identified from this interview."],
        weaknesses=weaknesses or ["No significant weaknesses were identified."],
        technical_skill_gaps=technical_skill_gaps,
        communication_improvements=communication_improvements,
        interview_highlights=interview_highlights,
        recommended_preparation=recommended_preparation
        or ["Enable a real AI provider for more specific preparation guidance."],
        improvement_plan=improvement_plan,
        source="heuristic_v1",
        model_version=None,
    )
