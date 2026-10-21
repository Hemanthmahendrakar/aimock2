"""
Provider interfaces for speech-to-text, text-to-speech, and avatar
session creation. Each has exactly one method — these are deliberately
narrow abstractions, not general-purpose provider SDK wrappers.

Unlike app/ai/providers/base.py's evaluate_*/generate_* methods, there
is no meaningful "heuristic" implementation of any of these three —
you cannot approximate speech synthesis or lip-synced video without
actually doing it. So instead of a HeuristicProvider that does
real (if limited) work, the "none" case here is a NullProvider that
explicitly returns "not configured," and callers (routes/services) are
expected to treat that as a normal, expected state — not an error to
surface to the user as a failure.
"""
from abc import ABC, abstractmethod

from app.voice.types import TranscriptionResult, SpeechResult, AvatarSession


class VoiceProviderError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, *, audio_bytes: bytes, content_type: str) -> TranscriptionResult: ...


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, *, text: str, voice_id: str | None) -> SpeechResult: ...


class AvatarProvider(ABC):
    @abstractmethod
    def create_session(self, *, avatar_id: str | None) -> AvatarSession: ...
