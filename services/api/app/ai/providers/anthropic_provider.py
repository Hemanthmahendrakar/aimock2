"""
Anthropic-backed provider. Used when AI_PROVIDER="anthropic" and
AI_API_KEY is set.

IMPORTANT CAVEAT: this was written without network access to actually
exercise it against the real Anthropic API. The request/response shape
follows the public Messages API, and JSON parsing is defensive (strips
code fences, catches malformed output), but it has not been run
end-to-end. Treat it as a first draft to verify before relying on it
in production — see the module docstring in app/ai/gateway.py for how
failures here are handled (fall back to the heuristic provider rather
than break the request).
"""
import json
import re

import requests

from app.ai.providers.base import AIProvider, AIProviderError
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

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class AnthropicProvider(AIProvider):
    def __init__(self, *, api_key: str, model: str, base_url: str, timeout_seconds: int):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    # ------------------------------------------------------------------
    def analyze_resume(self, resume_text: str) -> ResumeAnalysis:
        system_prompt = (
            "You extract structured candidate information from resume text. "
            "Respond with ONLY a JSON object, no preamble, no markdown fences. "
            "Keys: education, skills, programming_languages, technologies, "
            "projects, internships, experience, certifications, achievements. "
            "Every value is an array of short strings. If a section isn't "
            "present in the resume, use an empty array for it. Never invent "
            "information not present in the text."
        )
        data = self._call_json(
            system=system_prompt,
            user=f"Resume text:\n\n{resume_text[:12000]}",
            max_tokens=2000,
        )
        fields = {
            k: data.get(k, [])
            for k in (
                "education", "skills", "programming_languages", "technologies",
                "projects", "internships", "experience", "certifications", "achievements",
            )
        }
        return ResumeAnalysis(**fields, extraction_method="ai_v1")

    def generate_question(self, context: QuestionContext) -> GeneratedQuestion:
        system_prompt = (
            "You are a professional, restrained mock interviewer. You never "
            "use effusive praise like 'Great answer!' or 'Excellent!'. Generate "
            "exactly one interview question appropriate for the given round, "
            "difficulty, role, and candidate background. Do not repeat any "
            "question already asked. Respond with ONLY a JSON object: "
            '{"question": "..."}. No preamble, no markdown fences.'
        )
        user_prompt = (
            f"Round: {context.round_type}\n"
            f"Difficulty: {context.difficulty}\n"
            f"Target role: {context.target_role}\n"
            f"Experience level: {context.experience_level or 'unspecified'}\n"
            f"Question categories/focus areas: {', '.join(context.question_categories) or 'general'}\n"
            f"Round instructions: {context.instructions or 'none'}\n"
            f"Candidate skills: {', '.join(context.candidate_profile.get('skills', [])) or 'unknown'}\n"
            f"Candidate projects: {'; '.join(context.candidate_profile.get('projects', [])) or 'unknown'}\n"
            f"Questions already asked this round: {context.previous_questions or 'none'}\n"
            f"Seconds remaining in round: {context.seconds_remaining}"
        )
        data = self._call_json(system=system_prompt, user=user_prompt, max_tokens=500)
        question_text = data.get("question")
        if not question_text or not isinstance(question_text, str):
            raise AIProviderError("Anthropic response missing a valid 'question' field.")
        return GeneratedQuestion(question_text=question_text, source="ai_v1")

    def generate_followup(self, context: FollowupContext) -> GeneratedQuestion | None:
        system_prompt = (
            "You are a professional, restrained mock interviewer. Decide "
            "whether the candidate's answer warrants a follow-up question — "
            "e.g. it was vague, incomplete, or invites a natural probe (like "
            "asking about their specific contribution to a project they "
            "mentioned). If a follow-up is warranted, phrase it in a "
            "restrained, professional tone (never 'Great answer!' or similar "
            "praise). If the answer was already thorough, no follow-up is "
            "needed. Respond with ONLY a JSON object: "
            '{"followup_needed": true/false, "question": "..." or null}. '
            "No preamble, no markdown fences."
        )
        user_prompt = (
            f"Round: {context.round_type}\n"
            f"Difficulty: {context.difficulty}\n"
            f"Round instructions: {context.instructions or 'none'}\n"
            f"Original question: {context.original_question}\n"
            f"Candidate's answer: {context.answer_text}\n"
            f"Follow-ups already asked for this question: {context.followups_asked_so_far}"
        )
        data = self._call_json(system=system_prompt, user=user_prompt, max_tokens=300)
        if not data.get("followup_needed"):
            return None
        question_text = data.get("question")
        if not question_text or not isinstance(question_text, str):
            return None
        return GeneratedQuestion(question_text=question_text, source="ai_v1")

    # ------------------------------------------------------------------
    def evaluate_answer(self, context: RoundEvaluationContext) -> EvaluationResult:
        system_prompt = (
            "You are an expert technical interviewer scoring a candidate's "
            f"performance in the {context.round_type} round, against exactly "
            f"these rubric criteria: {', '.join(context.criteria_names)}. Score "
            "each criterion 0-100 based ONLY on what the candidate actually said "
            "— never invent claims they didn't make. Ground every score in "
            "specific evidence quoted or closely paraphrased from their answers. "
            "Do NOT make personality or psychological judgments (e.g. about "
            "confidence, intelligence, or character) — evaluate only the "
            "content of what was said against the rubric. Respond with ONLY a "
            "JSON object: {\"criteria_scores\": {criterion: 0-100, ...}, "
            "\"overall_score\": 0-100, \"evidence\": [\"...\"], "
            "\"strengths\": [\"...\"], \"weaknesses\": [\"...\"], "
            "\"improvement_suggestions\": [\"...\"]}. No preamble, no markdown fences."
        )
        qa_text = "\n\n".join(
            f"Q ({a.topic or 'general'}): {a.question_text}\nA: {a.answer_text}"
            for a in context.answers
        )
        user_prompt = (
            f"Round: {context.round_type}\n"
            f"Difficulty: {context.difficulty}\n"
            f"Target role: {context.target_role}\n"
            f"Round instructions: {context.instructions or 'none'}\n\n"
            f"Questions and answers:\n{qa_text}"
        )
        data = self._call_json(system=system_prompt, user=user_prompt, max_tokens=1500)
        return self._parse_evaluation_result(
            data, dimension=context.round_type, criteria_names=context.criteria_names
        )

    def evaluate_communication(
        self, context: CommunicationEvaluationContext
    ) -> EvaluationResult:
        system_prompt = (
            "You are an expert interview coach scoring a candidate's "
            "communication across an entire mock interview, against exactly "
            "these criteria: clarity, structure, conciseness, fluency, pace, "
            "filler_words, repetition, relevance. Score each 0-100 based on "
            "HOW they communicated (not what they said content-wise — that's "
            "scored separately). Do NOT make personality or psychological "
            "judgments — evaluate only observable communication patterns "
            "(filler word usage, repetition, structure of responses, etc), "
            "grounded in specific evidence from their answers. Respond with "
            "ONLY a JSON object: {\"criteria_scores\": {criterion: 0-100, ...}, "
            "\"overall_score\": 0-100, \"evidence\": [\"...\"], "
            "\"strengths\": [\"...\"], \"weaknesses\": [\"...\"], "
            "\"improvement_suggestions\": [\"...\"]}. No preamble, no markdown fences."
        )
        qa_text = "\n\n".join(
            f"Q: {a.question_text}\nA: {a.answer_text}" for a in context.answers
        )
        data = self._call_json(
            system=system_prompt,
            user=f"Answers to evaluate:\n\n{qa_text}",
            max_tokens=1500,
        )
        return self._parse_evaluation_result(
            data,
            dimension="communication",
            criteria_names=[
                "clarity", "structure", "conciseness", "fluency",
                "pace", "filler_words", "repetition", "relevance",
            ],
        )

    def generate_report(self, context: ReportContext) -> ReportContent:
        system_prompt = (
            "You are writing a mock interview report for a candidate named "
            f"{context.student_name}, who interviewed for a {context.target_role} "
            f"role at {context.difficulty} difficulty. You are given four already-"
            "completed rubric evaluations (technical, managerial, hr, communication) "
            "— your job is to SYNTHESIZE them into a coherent report, not re-judge "
            "the candidate from scratch. Ground every point in the evaluations "
            "provided; do not invent claims not supported by them. Do NOT make "
            "personality or psychological judgments. Respond with ONLY a JSON "
            "object with these exact keys, each a list of short strings: "
            "\"strengths\", \"weaknesses\", \"technical_skill_gaps\", "
            "\"communication_improvements\", \"interview_highlights\", "
            "\"recommended_preparation\", \"improvement_plan\". No preamble, no "
            "markdown fences."
        )

        def _eval_block(label: str, e: EvaluationResult) -> str:
            return (
                f"{label} (score {e.score}/100):\n"
                f"  Criteria: {e.criteria_scores}\n"
                f"  Evidence: {e.evidence}\n"
                f"  Strengths: {e.strengths}\n"
                f"  Weaknesses: {e.weaknesses}\n"
                f"  Suggestions: {e.improvement_suggestions}"
            )

        user_prompt = "\n\n".join(
            [
                _eval_block("Technical", context.technical_eval),
                _eval_block("Managerial", context.managerial_eval),
                _eval_block("HR", context.hr_eval),
                _eval_block("Communication", context.communication_eval),
            ]
        )
        data = self._call_json(system=system_prompt, user=user_prompt, max_tokens=2000)

        def _str_list(key: str) -> list[str]:
            val = data.get(key)
            return [str(v) for v in val] if isinstance(val, list) else []

        return ReportContent(
            strengths=_str_list("strengths"),
            weaknesses=_str_list("weaknesses"),
            technical_skill_gaps=_str_list("technical_skill_gaps"),
            communication_improvements=_str_list("communication_improvements"),
            interview_highlights=_str_list("interview_highlights"),
            recommended_preparation=_str_list("recommended_preparation"),
            improvement_plan=_str_list("improvement_plan"),
            source="ai_v1",
            model_version=self._model,
        )

    def _parse_evaluation_result(
        self, data: dict, *, dimension: str, criteria_names: list[str]
    ) -> EvaluationResult:
        criteria_scores = data.get("criteria_scores")
        if not isinstance(criteria_scores, dict):
            raise AIProviderError("Anthropic response missing 'criteria_scores'.")
        # Clamp to known criteria/range defensively — never trust an
        # external model's output shape blindly.
        clean_scores = {}
        for name in criteria_names:
            raw = criteria_scores.get(name)
            if not isinstance(raw, (int, float)):
                raise AIProviderError(f"Missing or invalid score for criterion '{name}'.")
            clean_scores[name] = max(0, min(100, round(raw)))

        overall = data.get("overall_score")
        if not isinstance(overall, (int, float)):
            overall = sum(clean_scores.values()) / len(clean_scores)
        overall = max(0, min(100, round(overall)))

        def _str_list(key: str) -> list[str]:
            val = data.get(key)
            return [str(v) for v in val] if isinstance(val, list) else []

        return EvaluationResult(
            dimension=dimension,
            score=overall,
            criteria_scores=clean_scores,
            evidence=_str_list("evidence"),
            strengths=_str_list("strengths"),
            weaknesses=_str_list("weaknesses"),
            improvement_suggestions=_str_list("improvement_suggestions"),
            source="ai_v1",
        )

    # ------------------------------------------------------------------
    def _call_json(self, *, system: str, user: str, max_tokens: int) -> dict:
        if not self._api_key:
            raise AIProviderError("AI_API_KEY is not configured.")

        try:
            response = requests.post(
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise AIProviderError(f"Anthropic API request failed: {exc}") from exc

        try:
            body = response.json()
            text_blocks = [
                block["text"] for block in body.get("content", []) if block.get("type") == "text"
            ]
            raw_text = "".join(text_blocks).strip()
        except (KeyError, ValueError) as exc:
            raise AIProviderError(f"Unexpected Anthropic response shape: {exc}") from exc

        cleaned = _JSON_FENCE_RE.sub("", raw_text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIProviderError(f"Anthropic did not return valid JSON: {exc}") from exc
