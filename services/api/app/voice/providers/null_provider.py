"""
Default providers when STT_PROVIDER/TTS_PROVIDER/AVATAR_PROVIDER are
unset ("none" — the default, and what tests run against). These are
not stand-ins for real functionality the way HeuristicProvider is for
the AI Gateway; they're honest "not configured" signals. See
providers/base.py for why there's no heuristic equivalent here.
"""
from app.voice.providers.base import STTProvider, TTSProvider, AvatarProvider
from app.voice.types import TranscriptionResult, SpeechResult, AvatarSession


class NullSTTProvider(STTProvider):
    def transcribe(self, *, audio_bytes: bytes, content_type: str) -> TranscriptionResult:
        # No fabricated transcript — callers must treat an empty result
        # as "ask the student to type their answer instead," never as
        # a real (if wrong) transcription.
        return TranscriptionResult(text="", source="unavailable")


class NullTTSProvider(TTSProvider):
    def synthesize(self, *, text: str, voice_id: str | None) -> SpeechResult:
        return SpeechResult(audio_bytes=None, content_type=None, source="browser_fallback")


class NullAvatarProvider(AvatarProvider):
    def create_session(self, *, avatar_id: str | None) -> AvatarSession:
        return AvatarSession(provider="none")
