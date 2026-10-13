"""
Speech-to-text via OpenAI's Whisper API. Like
app/ai/providers/anthropic_provider.py (Phase 8), this was written
without network access to actually exercise it — verify against the
real API before relying on it in production. Same defensive posture:
API key never logged, never in error text; failures raise
VoiceProviderError rather than propagating a raw exception, so the
route can decide how to respond (see interview_session.py).
"""
import requests

from app.voice.providers.base import STTProvider, VoiceProviderError
from app.voice.types import TranscriptionResult


class WhisperSTTProvider(STTProvider):
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout_seconds: int):
        if not api_key:
            raise VoiceProviderError("STT_API_KEY is not configured.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    def transcribe(self, *, audio_bytes: bytes, content_type: str) -> TranscriptionResult:
        ext = {"audio/webm": "webm", "audio/wav": "wav", "audio/mpeg": "mp3",
               "audio/ogg": "ogg", "audio/mp4": "mp4"}.get(content_type, "webm")
        try:
            response = requests.post(
                f"{self._base_url}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (f"answer.{ext}", audio_bytes, content_type)},
                data={"model": self._model},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VoiceProviderError(f"STT request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise VoiceProviderError(f"STT returned non-JSON response: {exc}") from exc

        text = data.get("text")
        if not isinstance(text, str):
            raise VoiceProviderError("STT response did not include a text field.")

        return TranscriptionResult(text=text.strip(), source="whisper_v1")
