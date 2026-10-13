"""
Provider interface for the AI Gateway. The rest of the app (resume
pipeline, interview engine, evaluation engine, report generation)
depends only on AIGateway, never on a concrete provider — swapping
providers means changing AI_PROVIDER in config, not touching
interview_service.py, resume_tasks.py, or evaluation_service.py.

generate_report() (Phase 11) is the sixth and last function the
spec's AI GATEWAY section names — the provider interface is now
complete.
"""
from abc import ABC, abstractmethod

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


class AIProviderError(Exception):
    """Raised by a provider on failure; AIGateway catches this to fall
    back to the heuristic provider rather than let a request fail."""


class AIProvider(ABC):
    @abstractmethod
    def analyze_resume(self, resume_text: str) -> ResumeAnalysis: ...

    @abstractmethod
    def generate_question(self, context: QuestionContext) -> GeneratedQuestion: ...

    @abstractmethod
    def generate_followup(self, context: FollowupContext) -> GeneratedQuestion | None: ...

    @abstractmethod
    def evaluate_answer(self, context: RoundEvaluationContext) -> EvaluationResult: ...

    @abstractmethod
    def evaluate_communication(
        self, context: CommunicationEvaluationContext
    ) -> EvaluationResult: ...

    @abstractmethod
    def generate_report(self, context: ReportContext) -> ReportContent: ...
