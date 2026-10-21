"""
Deterministic, no-network evaluators backing HeuristicProvider
(AI_PROVIDER="none", and what tests run against).

IMPORTANT DISTINCTION between the two functions here:

- evaluate_communication_heuristically(): a REAL implementation. The
  spec explicitly calls out "filler words where technically
  measurable" — filler-word ratio, repetition, and pace (words/minute,
  using InterviewAnswer.time_taken_seconds) are genuinely computable
  without language understanding. Clarity/structure/relevance are
  approximated from those same signals and are honestly weaker proxies
  — noted in the returned evidence, not overclaimed.

- evaluate_round_heuristically(): NOT a real content judge. Assessing
  whether an answer is technically CORRECT, or whether a decision was
  actually good judgment, requires understanding the words, not just
  counting them. This function scores response completeness (did they
  answer, how substantively) and applies that same score across every
  rubric criterion, with an explicit evidence line saying so. This is
  intentionally honest rather than a heuristic dressed up to look like
  real grading — see AIGateway/AnthropicProvider for the real thing.
"""
import re

from app.ai.types import RoundEvaluationContext, CommunicationEvaluationContext, EvaluationResult
from app.services.evaluation_rubrics import criteria_for_dimension
from app.models import EvaluationDimension

_FILLER_WORDS = (
    "um", "uh", "umm", "uhh", "like", "you know", "i mean", "sort of",
    "kind of", "basically", "actually", "literally", "so yeah",
)

# Very common structural/stop words excluded from repetition scoring —
# their natural repetition isn't meaningful the way repeating a content
# word ("the API... the API... the API...") is.
_STOPWORDS = frozenset(
    "the a an is are was were be been being to of in on at for and or "
    "but if then so it its this that these those i you he she we they "
    "my your his her our their with as by from".split()
)

_IDEAL_WPM_RANGE = (100, 160)
_IDEAL_ANSWER_WORD_RANGE = (25, 150)


def _word_count(text: str) -> int:
    return len(text.split())


def _count_filler_words(text: str) -> int:
    lowered = text.lower()
    return sum(len(re.findall(rf"\b{re.escape(phrase)}\b", lowered)) for phrase in _FILLER_WORDS)


def _repeated_content_word_ratio(text: str) -> float:
    words = [w.strip(".,!?;:").lower() for w in text.split()]
    content_words = [w for w in words if w and w not in _STOPWORDS]
    if not content_words:
        return 0.0
    counts: dict[str, int] = {}
    for w in content_words:
        counts[w] = counts.get(w, 0) + 1
    repeated = sum(c - 1 for c in counts.values() if c > 1)
    return repeated / len(content_words)


def _triangular_score(value: float, low: float, high: float) -> float:
    """100 within [low, high], falling off linearly outside it."""
    if low <= value <= high:
        return 100.0
    span = (high - low) or 1.0
    if value < low:
        return max(0.0, 100.0 - (low - value) / span * 100.0)
    return max(0.0, 100.0 - (value - high) / span * 100.0)


def evaluate_communication_heuristically(
    context: CommunicationEvaluationContext,
) -> EvaluationResult:
    answers = context.answers
    if not answers:
        return EvaluationResult(
            dimension=EvaluationDimension.COMMUNICATION,
            score=0,
            criteria_scores={c: 0 for c in criteria_for_dimension(EvaluationDimension.COMMUNICATION)},
            evidence=["No answers were recorded to evaluate."],
            strengths=[],
            weaknesses=["No answers were recorded."],
            improvement_suggestions=[],
            source="heuristic_v1",
        )

    total_words = 0
    total_fillers = 0
    filler_examples: list[str] = []
    repetition_ratios = []
    wpm_samples = []

    for a in answers:
        words = _word_count(a.answer_text)
        total_words += words
        fillers = _count_filler_words(a.answer_text)
        total_fillers += fillers
        if fillers and len(filler_examples) < 3:
            found = [p for p in _FILLER_WORDS if re.search(rf"\b{re.escape(p)}\b", a.answer_text.lower())]
            filler_examples.extend(found[: 3 - len(filler_examples)])

        repetition_ratios.append(_repeated_content_word_ratio(a.answer_text))

        if a.time_taken_seconds and a.time_taken_seconds > 0 and words > 0:
            wpm_samples.append(words / (a.time_taken_seconds / 60))

    avg_words_per_answer = total_words / len(answers)
    filler_ratio = total_fillers / total_words if total_words else 0.0
    avg_repetition_ratio = sum(repetition_ratios) / len(repetition_ratios)
    avg_wpm = sum(wpm_samples) / len(wpm_samples) if wpm_samples else None

    filler_score = max(0.0, 100.0 - min(100.0, filler_ratio * 300.0))
    repetition_score = max(0.0, 100.0 - min(100.0, avg_repetition_ratio * 200.0))
    conciseness_score = _triangular_score(avg_words_per_answer, *_IDEAL_ANSWER_WORD_RANGE)
    pace_score = _triangular_score(avg_wpm, *_IDEAL_WPM_RANGE) if avg_wpm is not None else 65.0
    # Weaker proxies — no independent measurement, honestly noted below.
    fluency_score = (filler_score + pace_score) / 2
    clarity_score = (repetition_score + conciseness_score) / 2
    structure_score = 65.0
    relevance_score = 65.0

    criteria_scores = {
        "clarity": round(clarity_score),
        "structure": round(structure_score),
        "conciseness": round(conciseness_score),
        "fluency": round(fluency_score),
        "pace": round(pace_score),
        "filler_words": round(filler_score),
        "repetition": round(repetition_score),
        "relevance": round(relevance_score),
    }
    overall = round(sum(criteria_scores.values()) / len(criteria_scores))

    evidence = [
        f"Detected {total_fillers} filler word(s) across {len(answers)} answer(s)"
        + (f" (e.g. {', '.join(sorted(set(filler_examples)))})" if filler_examples else "") + ".",
        f"Average response length: {avg_words_per_answer:.0f} words.",
    ]
    if avg_wpm is not None:
        evidence.append(f"Average speaking pace: {avg_wpm:.0f} words/minute.")
    evidence.append(
        "Clarity, structure, and relevance are approximated from repetition/length/pace "
        "signals, not independently assessed — heuristic evaluation only."
    )

    strengths = []
    weaknesses = []
    if filler_score >= 80:
        strengths.append("Minimal filler-word usage.")
    else:
        weaknesses.append("Noticeable filler-word usage (e.g. 'um', 'like').")
    if repetition_score >= 80:
        strengths.append("Answers avoided repeating the same points.")
    else:
        weaknesses.append("Some repetition of the same words/phrases within answers.")
    if avg_wpm is not None and not (_IDEAL_WPM_RANGE[0] <= avg_wpm <= _IDEAL_WPM_RANGE[1]):
        weaknesses.append(
            "Speaking pace was "
            + ("slower" if avg_wpm < _IDEAL_WPM_RANGE[0] else "faster")
            + " than a typical comfortable interview pace."
        )

    suggestions = []
    if filler_score < 80:
        suggestions.append("Practice pausing silently instead of using filler words.")
    if conciseness_score < 70:
        suggestions.append(
            "Aim for answers in roughly the 25-150 word range — enough detail without rambling."
        )
    if not suggestions:
        suggestions.append("Keep practicing to maintain this level of clarity under pressure.")

    return EvaluationResult(
        dimension=EvaluationDimension.COMMUNICATION,
        score=overall,
        criteria_scores=criteria_scores,
        evidence=evidence,
        strengths=strengths,
        weaknesses=weaknesses,
        improvement_suggestions=suggestions,
        source="heuristic_v1",
    )


def evaluate_round_heuristically(context: RoundEvaluationContext) -> EvaluationResult:
    dimension = context.round_type  # "technical" / "managerial" / "hr"
    criteria = criteria_for_dimension(dimension)
    answers = context.answers

    if not answers:
        return EvaluationResult(
            dimension=dimension,
            score=0,
            criteria_scores={c: 0 for c in criteria},
            evidence=["No answers were recorded for this round."],
            strengths=[],
            weaknesses=["No answers were recorded."],
            improvement_suggestions=[],
            source="heuristic_v1",
        )

    avg_words = sum(_word_count(a.answer_text) for a in answers) / len(answers)
    # Structural-completeness proxy only — see module docstring. Capped
    # well short of 100 so a long-but-wrong answer can never look like
    # a strong heuristic score; this is a floor-level signal, not a
    # confident assessment.
    completeness_score = round(min(70.0, avg_words / _IDEAL_ANSWER_WORD_RANGE[1] * 70.0))
    criteria_scores = {c: completeness_score for c in criteria}

    evidence = [
        f"{len(answers)} question(s) answered in this round, "
        f"averaging {avg_words:.0f} words per answer.",
        "This score reflects response completeness only (heuristic evaluation) — "
        "content correctness and reasoning quality were not assessed. Configure "
        "AI_PROVIDER=anthropic for content-aware evaluation.",
    ]
    strengths = (
        ["Answered every question in this round with substantive responses."]
        if avg_words >= 40
        else []
    )
    weaknesses = (
        ["Some answers were brief; consider elaborating with specific examples."]
        if avg_words < 40
        else []
    )
    suggestions = [
        "Enable a real AI provider for feedback on technical accuracy, reasoning "
        "quality, and depth beyond response length."
    ]

    return EvaluationResult(
        dimension=dimension,
        score=completeness_score,
        criteria_scores=criteria_scores,
        evidence=evidence,
        strengths=strengths,
        weaknesses=weaknesses,
        improvement_suggestions=suggestions,
        source="heuristic_v1",
    )
