"""
Voice/avatar gateway. Same shape as app/ai/gateway.py: the rest of the
app depends only on this module, never on a specific provider class,
so swapping STT/TTS/avatar vendors is a config change.

Unlike AIGateway, a provider failure here does NOT fall back to a
"lesser but working" implementation — there is no heuristic speech
synthesis. Instead, a configured-but-failing provider raises
VoiceProviderError up to the caller, and a provider that was never
configured returns the Null* result type (empty transcript / no audio
/ no avatar session) without attempting a call at all. Callers (routes)
distinguish these two cases deliberately — see interview_session.py.
"""
import logging

from flask import current_app

from app.voice.providers.base import VoiceProviderError
from app.voice.providers.null_provider import (
    NullSTTProvider,
    NullTTSProvider,
    NullAvatarProvider,
)
from app.voice.types import TranscriptionResult, SpeechResult, AvatarSession

logger = logging.getLogger("app.voice")


class VoiceGateway:
    def __init__(self):
        cfg = current_app.config
        self._stt_provider_name = cfg["STT_PROVIDER"]
        self._tts_provider_name = cfg["TTS_PROVIDER"]
        self._avatar_provider_name = cfg["AVATAR_PROVIDER"]

    def transcribe(self, *, audio_bytes: bytes, content_type: str) -> TranscriptionResult:
        if self._stt_provider_name == "none":
            return NullSTTProvider().transcribe(audio_bytes=audio_bytes, content_type=content_type)

        if self._stt_provider_name == "whisper":
            from app.voice.providers.whisper_provider import WhisperSTTProvider

            cfg = current_app.config
            provider = WhisperSTTProvider(
                api_key=cfg["STT_API_KEY"], base_url=cfg["STT_API_BASE_URL"],
                model=cfg["STT_MODEL"], timeout_seconds=cfg["VOICE_REQUEST_TIMEOUT_SECONDS"],
            )
            return provider.transcribe(audio_bytes=audio_bytes, content_type=content_type)

        raise VoiceProviderError(f"Unknown STT_PROVIDER: {self._stt_provider_name}")

    def synthesize(self, *, text: str, voice_id: str | None = None) -> SpeechResult:
        if self._tts_provider_name == "none":
            return NullTTSProvider().synthesize(text=text, voice_id=voice_id)

        if self._tts_provider_name == "elevenlabs":
            from app.voice.providers.elevenlabs_provider import ElevenLabsTTSProvider

            cfg = current_app.config
            provider = ElevenLabsTTSProvider(
                api_key=cfg["TTS_API_KEY"], base_url=cfg["TTS_API_BASE_URL"],
                default_voice_id=cfg["TTS_DEFAULT_VOICE_ID"],
                timeout_seconds=cfg["VOICE_REQUEST_TIMEOUT_SECONDS"],
            )
            return provider.synthesize(text=text, voice_id=voice_id)

        raise VoiceProviderError(f"Unknown TTS_PROVIDER: {self._tts_provider_name}")

    def create_avatar_session(self, *, avatar_id: str | None = None) -> AvatarSession:
        if self._avatar_provider_name == "none":
            return NullAvatarProvider().create_session(avatar_id=avatar_id)

        if self._avatar_provider_name == "generic":
            from app.voice.providers.generic_avatar_provider import GenericAvatarProvider

            cfg = current_app.config
            provider = GenericAvatarProvider(
                api_key=cfg["AVATAR_API_KEY"], base_url=cfg["AVATAR_API_BASE_URL"],
                default_avatar_id=cfg["AVATAR_DEFAULT_ID"],
                timeout_seconds=cfg["VOICE_REQUEST_TIMEOUT_SECONDS"],
            )
            return provider.create_session(avatar_id=avatar_id)

        raise VoiceProviderError(f"Unknown AVATAR_PROVIDER: {self._avatar_provider_name}")
