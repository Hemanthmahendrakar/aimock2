"""
Types shared across the STT/TTS/Avatar provider interfaces. Deliberately
separate from app/ai/types.py — the AI Gateway (Phase 8-11) reasons about
interview content; this module reasons about audio/video I/O. They're
independent abstractions that happen to both feed the same interview
flow, not one system.
"""
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    text: str
    source: str  # e.g. "whisper_v1" / "unavailable"
    confidence: float | None = None  # 0-1, when the provider reports one


@dataclass
class SpeechResult:
    """
    audio_bytes is None when no server-side TTS is configured — the
    caller (route) treats that as "let the browser's own speechSynthesis
    handle it," not as an error. See TTSProvider docstring.
    """
    audio_bytes: bytes | None
    content_type: str | None  # e.g. "audio/mpeg"
    source: str  # e.g. "elevenlabs_v1" / "browser_fallback"


@dataclass
class AvatarSession:
    """
    provider is "none" when no avatar provider is configured — the
    frontend renders its static fallback illustration in that case,
    same pattern as SpeechResult.audio_bytes being None.
    """
    provider: str
    embed_url: str | None = None
    session_token: str | None = None
    avatar_id: str | None = None
