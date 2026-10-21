"""
AI Gateway. Nothing outside app/ai/ should import a concrete provider
directly — this is the one seam the rest of the app depends on, so
swapping providers (or eventually a self-hosted model behind vLLM) is
a config change, never a code change in interview_service.py or
resume_tasks.py.

Resilience: if the configured real provider raises AIProviderError
(network failure, bad response shape, malformed JSON), the gateway
logs it and falls back to the heuristic provider for that single call
rather than let the request fail. A resume stuck "processing" forever
or an interview that can't produce its next question is worse than a
lower-quality heuristic result. The failure is logged either way so
it's visible in monitoring, not silently swallowed.
"""
import logging

from flask import current_app

from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.providers.heuristic_provider import HeuristicProvider
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

logger = logging.getLogger("app.ai.gateway")


def _build_provider(name: str) -> AIProvider:
    if name == "anthropic":
        from app.ai.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=current_app.config["AI_API_KEY"],
            model=current_app.config["AI_MODEL"],
            base_url=current_app.config["AI_API_BASE_URL"],
            timeout_seconds=current_app.config["AI_REQUEST_TIMEOUT_SECONDS"],
        )
    # "none" or anything unrecognized: heuristic. Never raise here for
    # an unknown provider name — config typos shouldn't break the app,
    # they should degrade to the safe default.
    return HeuristicProvider()


class AIGateway:
    def __init__(self):
        provider_name = current_app.config.get("AI_PROVIDER", "none")
        self._provider_name = provider_name
        self._provider = _build_provider(provider_name)
        self._fallback = HeuristicProvider()

    def _with_fallback(self, fn_name: str, primary_call, fallback_call):
        if isinstance(self._provider, HeuristicProvider):
            return primary_call()
        try:
            return primary_call()
        except AIProviderError as exc:
            logger.warning(
                "AI provider '%s' failed on %s, falling back to heuristic: %s",
                self._provider_name, fn_name, exc,
            )
            return fallback_call()

    def analyze_resume(self, resume_text: str) -> ResumeAnalysis:
        return self._with_fallback(
            "analyze_resume",
            lambda: self._provider.analyze_resume(resume_text),
            lambda: self._fallback.analyze_resume(resume_text),
        )

    def generate_question(self, context: QuestionContext) -> GeneratedQuestion:
        return self._with_fallback(
            "generate_question",
            lambda: self._provider.generate_question(context),
            lambda: self._fallback.generate_question(context),
        )

    def generate_followup(self, context: FollowupContext) -> GeneratedQuestion | None:
        return self._with_fallback(
            "generate_followup",
            lambda: self._provider.generate_followup(context),
            lambda: self._fallback.generate_followup(context),
        )

    def evaluate_answer(self, context: RoundEvaluationContext) -> EvaluationResult:
        return self._with_fallback(
            "evaluate_answer",
            lambda: self._provider.evaluate_answer(context),
            lambda: self._fallback.evaluate_answer(context),
        )

    def evaluate_communication(
        self, context: CommunicationEvaluationContext
    ) -> EvaluationResult:
        return self._with_fallback(
            "evaluate_communication",
            lambda: self._provider.evaluate_communication(context),
            lambda: self._fallback.evaluate_communication(context),
        )

    def generate_report(self, context: ReportContext) -> ReportContent:
        return self._with_fallback(
            "generate_report",
            lambda: self._provider.generate_report(context),
            lambda: self._fallback.generate_report(context),
        )
