"""
Text-to-speech via ElevenLabs. Same untested-without-network caveat as
whisper_provider.py — verify before production use.
"""
import requests

from app.voice.providers.base import TTSProvider, VoiceProviderError
from app.voice.types import SpeechResult


class ElevenLabsTTSProvider(TTSProvider):
    def __init__(
        self, *, api_key: str, base_url: str, default_voice_id: str, timeout_seconds: int
    ):
        if not api_key:
            raise VoiceProviderError("TTS_API_KEY is not configured.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_voice_id = default_voice_id
        self._timeout = timeout_seconds

    def synthesize(self, *, text: str, voice_id: str | None) -> SpeechResult:
        resolved_voice_id = voice_id or self._default_voice_id
        if not resolved_voice_id:
            raise VoiceProviderError(
                "No voice_id given and TTS_DEFAULT_VOICE_ID is not configured."
            )
        # ElevenLabs caps input length; interview questions are short,
        # but truncate defensively rather than let an oversized request
        # fail opaquely.
        text = text[:2000]

        try:
            response = requests.post(
                f"{self._base_url}/v1/text-to-speech/{resolved_voice_id}",
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={"text": text, "model_id": "eleven_turbo_v2"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VoiceProviderError(f"TTS request failed: {exc}") from exc

        if not response.content:
            raise VoiceProviderError("TTS response contained no audio data.")

        return SpeechResult(
            audio_bytes=response.content, content_type="audio/mpeg", source="elevenlabs_v1"
        )
