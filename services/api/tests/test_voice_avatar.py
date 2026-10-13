"""
Tests for Phase 13 (Voice + Avatar). Everything here runs against the
default "none" providers — there is no network access in this
environment to test whisper_provider.py / elevenlabs_provider.py /
generic_avatar_provider.py against real APIs. What IS tested: the
null-provider fallback behavior, the gateway's dispatch logic, that a
misconfigured real provider fails BEFORE any network call (same
technique as test_ai_gateway.py's fallback test), and that the routes
built on top of all this respond correctly to the "not configured"
case (which is the default, and what most readers of this test suite
will actually be running against).
"""
from datetime import datetime, timezone
from io import BytesIO

from app.extensions import db
from app.models import User, UserStatus, Interview
from app.voice.gateway import VoiceGateway
from app.voice.providers.base import VoiceProviderError
from app.voice.providers.null_provider import (
    NullSTTProvider,
    NullTTSProvider,
    NullAvatarProvider,
)


def _register_and_activate(client, *, institute_name, institute_email, admin_email, password):
    payload = {
        "institute_name": institute_name,
        "institute_email": institute_email,
        "admin_full_name": "Admin",
        "admin_email": admin_email,
        "password": password,
    }
    client.post("/api/v1/institute/auth/register", json=payload)
    user = db.session.query(User).filter(User.email == admin_email).first()
    user.status = UserStatus.ACTIVE
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return user


def _login(client, email, password):
    return client.post(
        "/api/v1/institute/auth/login", json={"email": email, "password": password}
    )


def _start_interview(client, suffix: str) -> str:
    _register_and_activate(
        client,
        institute_name=f"Institute {suffix}",
        institute_email=f"admissions@{suffix}.example",
        admin_email=f"admin@{suffix}.example",
        password="SuperSecret123",
    )
    _login(client, f"admin@{suffix}.example", "SuperSecret123")

    student_resp = client.post(
        "/api/v1/institute/students",
        json={"name": "Student", "email": f"{suffix}s1@students.example"},
    )
    student_id = student_resp.get_json()["data"]["id"]
    campaign_resp = client.post(
        "/api/v1/institute/campaigns", json={"name": f"{suffix} Drive", "role": "Dev"}
    )
    campaign_id = campaign_resp.get_json()["data"]["id"]
    client.post(
        f"/api/v1/institute/campaigns/{campaign_id}/students",
        json={"student_ids": [student_id]},
    )
    client.post(f"/api/v1/institute/campaigns/{campaign_id}/activate")

    import uuid as uuid_mod
    from app.utils.security import generate_raw_token, hash_token

    interview = (
        db.session.query(Interview)
        .filter(
            Interview.campaign_id == uuid_mod.UUID(campaign_id),
            Interview.student_id == uuid_mod.UUID(student_id),
        )
        .first()
    )
    raw_token = generate_raw_token()
    interview.access_token_hash = hash_token(raw_token)
    db.session.commit()
    interview_id = str(interview.id)

    client.post(f"/api/v1/interview/{interview_id}/access", json={"token": raw_token})
    client.post("/api/v1/interview/resume-check")
    client.post("/api/v1/interview/device-check")
    client.post("/api/v1/interview/start")
    return interview_id


# Minimal valid WebM header (EBML magic bytes) — enough to pass
# file-signature validation without being a real playable recording.
_FAKE_WEBM_BYTES = b"\x1aE\xdf\xa3" + b"\x00" * 32


class TestNullProviders:
    def test_null_stt_returns_empty_text_not_fabricated_transcript(self):
        result = NullSTTProvider().transcribe(audio_bytes=b"anything", content_type="audio/webm")
        assert result.text == ""
        assert result.source == "unavailable"

    def test_null_tts_returns_no_audio(self):
        result = NullTTSProvider().synthesize(text="Hello", voice_id=None)
        assert result.audio_bytes is None
        assert result.source == "browser_fallback"

    def test_null_avatar_returns_none_provider(self):
        session = NullAvatarProvider().create_session(avatar_id=None)
        assert session.provider == "none"
        assert session.embed_url is None


class TestVoiceGatewayDispatch:
    def test_gateway_uses_null_stt_by_default(self, app):
        with app.app_context():
            result = VoiceGateway().transcribe(audio_bytes=b"x", content_type="audio/webm")
            assert result.source == "unavailable"

    def test_gateway_uses_null_tts_by_default(self, app):
        with app.app_context():
            result = VoiceGateway().synthesize(text="Hello")
            assert result.audio_bytes is None

    def test_gateway_uses_null_avatar_by_default(self, app):
        with app.app_context():
            session = VoiceGateway().create_avatar_session()
            assert session.provider == "none"

    def test_unknown_stt_provider_name_raises(self, app):
        app.config["STT_PROVIDER"] = "some_unsupported_vendor"
        try:
            with app.app_context():
                try:
                    VoiceGateway().transcribe(audio_bytes=b"x", content_type="audio/webm")
                    assert False, "Expected VoiceProviderError"
                except VoiceProviderError:
                    pass
        finally:
            app.config["STT_PROVIDER"] = "none"


class TestRealProvidersFailFastWithoutCredentials:
    """
    Mirrors test_ai_gateway.py's TestGatewayFallback technique: a
    misconfigured real provider must fail BEFORE attempting any network
    call, so this is testable without network access.
    """

    def test_whisper_provider_requires_api_key(self, app):
        from app.voice.providers.whisper_provider import WhisperSTTProvider

        with app.app_context():
            try:
                WhisperSTTProvider(
                    api_key="", base_url="https://api.openai.com", model="whisper-1",
                    timeout_seconds=30,
                )
                assert False, "Expected VoiceProviderError"
            except VoiceProviderError:
                pass

    def test_elevenlabs_provider_requires_api_key(self, app):
        from app.voice.providers.elevenlabs_provider import ElevenLabsTTSProvider

        with app.app_context():
            try:
                ElevenLabsTTSProvider(
                    api_key="", base_url="https://api.elevenlabs.io",
                    default_voice_id="", timeout_seconds=30,
                )
                assert False, "Expected VoiceProviderError"
            except VoiceProviderError:
                pass

    def test_generic_avatar_provider_requires_api_key(self, app):
        from app.voice.providers.generic_avatar_provider import GenericAvatarProvider

        with app.app_context():
            try:
                GenericAvatarProvider(
                    api_key="", base_url="https://example.com",
                    default_avatar_id="", timeout_seconds=30,
                )
                assert False, "Expected VoiceProviderError"
            except VoiceProviderError:
                pass


class TestTranscribeRoute:
    def test_requires_session(self, client):
        resp = client.post(
            "/api/v1/interview/transcribe",
            data={"file": (BytesIO(_FAKE_WEBM_BYTES), "answer.webm")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 401

    def test_missing_file_rejected(self, client):
        _start_interview(client, "tr1")
        resp = client.post("/api/v1/interview/transcribe", data={})
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "missing_file"

    def test_invalid_audio_bytes_rejected(self, client):
        _start_interview(client, "tr2")
        resp = client.post(
            "/api/v1/interview/transcribe",
            data={"file": (BytesIO(b"not real audio data"), "answer.webm")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_file"

    def test_valid_audio_with_no_stt_configured_returns_501(self, client):
        _start_interview(client, "tr3")
        resp = client.post(
            "/api/v1/interview/transcribe",
            data={"file": (BytesIO(_FAKE_WEBM_BYTES), "answer.webm")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 501
        assert resp.get_json()["error"]["code"] == "stt_not_configured"


class TestQuestionAudioRoute:
    def test_requires_session(self, client):
        resp = client.get("/api/v1/interview/question-audio")
        assert resp.status_code == 401

    def test_no_tts_configured_returns_501(self, client):
        _start_interview(client, "qa1")
        resp = client.get("/api/v1/interview/question-audio")
        assert resp.status_code == 501
        assert resp.get_json()["error"]["code"] == "tts_not_configured"


class TestAvatarSessionRoute:
    def test_requires_session(self, client):
        resp = client.get("/api/v1/interview/avatar-session")
        assert resp.status_code == 401

    def test_no_avatar_configured_returns_none_provider(self, client):
        _start_interview(client, "av1")
        resp = client.get("/api/v1/interview/avatar-session")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["provider"] == "none"
        assert data["embed_url"] is None
