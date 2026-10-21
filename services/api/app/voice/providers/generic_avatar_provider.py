"""
Avatar session creation — a TEMPLATE, more explicitly so than the
other two real providers in this module.

For whisper_provider.py and elevenlabs_provider.py, the request/
response shapes reflect those providers' actual documented APIs
reasonably confidently, even though neither was tested against the
real network here. This file is different: your spec names no avatar
vendor, and avatar/talking-head APIs (D-ID, HeyGen, Synthesia, Tavus,
and others) vary in their exact request/response shape and change
over time — I don't have reliable enough knowledge of any one
vendor's current exact API to write code that should be trusted as-is.

What this DOES reflect accurately: the shape most session-based avatar
APIs share at a high level (POST to create a session for an avatar ID,
get back an embed URL and/or a short-lived client token). Treat the
endpoint path, payload keys, and response keys below as illustrative
placeholders — replace them with your chosen vendor's actual documented
API before relying on this in production. Do not assume the specific
strings here ("/v1/sessions", "avatar_id", etc.) are correct for any
real vendor.
"""
import requests

from app.voice.providers.base import AvatarProvider, VoiceProviderError
from app.voice.types import AvatarSession


class GenericAvatarProvider(AvatarProvider):
    def __init__(self, *, api_key: str, base_url: str, default_avatar_id: str, timeout_seconds: int):
        if not api_key:
            raise VoiceProviderError("AVATAR_API_KEY is not configured.")
        if not base_url:
            raise VoiceProviderError(
                "AVATAR_API_BASE_URL is not configured — set it to your chosen "
                "avatar provider's API base URL."
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_avatar_id = default_avatar_id
        self._timeout = timeout_seconds

    def create_session(self, *, avatar_id: str | None) -> AvatarSession:
        resolved_avatar_id = avatar_id or self._default_avatar_id
        if not resolved_avatar_id:
            raise VoiceProviderError(
                "No avatar_id given and AVATAR_DEFAULT_ID is not configured."
            )

        # PLACEHOLDER endpoint/payload shape — see module docstring.
        try:
            response = requests.post(
                f"{self._base_url}/v1/sessions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"avatar_id": resolved_avatar_id},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VoiceProviderError(f"Avatar session request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise VoiceProviderError(f"Avatar provider returned non-JSON response: {exc}") from exc

        embed_url = data.get("embed_url")
        session_token = data.get("session_token")
        if not embed_url and not session_token:
            raise VoiceProviderError(
                "Avatar provider response had neither embed_url nor session_token — "
                "check this matches your vendor's actual response shape."
            )

        return AvatarSession(
            provider="generic_v1",
            embed_url=embed_url,
            session_token=session_token,
            avatar_id=resolved_avatar_id,
        )
