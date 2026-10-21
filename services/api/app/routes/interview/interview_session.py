"""
Student-facing interview session routes. This is a completely
different trust boundary from /api/v1/institute/* — there is no
institute-admin user here at all. Access is proven once via a
one-time-link access token (POST /access), which issues a session JWT
scoped to exactly that interview (see require_interview_session).
Every other route reads g.current_interview, set by that decorator —
never a client-supplied interview_id in the body/query for anything
that mutates state.
"""
import uuid

from flask import Blueprint, request, g, current_app
from pydantic import ValidationError

from app.extensions import limiter
from app.schemas.interview_schemas import ExchangeAccessTokenRequest, SubmitAnswerRequest
from app.schemas.serializers_interview import serialize_interview_state, serialize_question_public
from app.schemas.serializers_report import serialize_report
from app.services.interview_service import InterviewService, InterviewServiceError
from app.repositories.report_repository import ReportRepository
from app.repositories.campaign_repository import CampaignRepository
from app.utils.authorization import require_interview_session
from app.utils.security import encode_jwt
from app.utils.responses import ok, error
from app.utils.file_validation import FileValidationError
from app.voice.gateway import VoiceGateway
from app.voice.providers.base import VoiceProviderError

bp = Blueprint("interview_session", __name__, url_prefix="/api/v1/interview")


def _validation_error_response(exc: ValidationError):
    details = [
        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return error("validation_error", "Invalid request data.", 422, details=details)


def _parse_uuid_or_none(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        return None


def _set_session_cookie(response, interview_id: uuid.UUID):
    token = encode_jwt(
        secret_key=current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
        subject=str(interview_id),
        ttl=current_app.config["INTERVIEW_SESSION_TOKEN_TTL"],
        extra_claims={"interview_id": str(interview_id)},
    )
    response.set_cookie(
        current_app.config["INTERVIEW_SESSION_COOKIE_NAME"],
        token,
        max_age=int(current_app.config["INTERVIEW_SESSION_TOKEN_TTL"].total_seconds()),
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite=current_app.config["COOKIE_SAMESITE"],
        domain=current_app.config["COOKIE_DOMAIN"],
        path="/api/v1/interview",
    )
    return response


@bp.post("/<interview_id>/access")
@limiter.limit("10 per hour")
def exchange_access(interview_id: str):
    parsed_id = _parse_uuid_or_none(interview_id)
    if parsed_id is None:
        return error("invalid_access_token", "This interview link is invalid.", 401)

    try:
        payload = ExchangeAccessTokenRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = InterviewService()
    try:
        interview = service.exchange_access_token(parsed_id, payload.token)
    except InterviewServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    response, status = ok(serialize_interview_state(interview))
    return _set_session_cookie(response, interview.id), status


@bp.get("/me")
@require_interview_session
def get_state():
    interview = g.current_interview
    service = InterviewService()
    current_question = service.get_current_question(interview)
    return ok(serialize_interview_state(interview, current_question=current_question))


@bp.post("/resume-check")
@require_interview_session
def resume_check():
    interview = InterviewService().mark_resume_verified(g.current_interview)
    return ok(serialize_interview_state(interview))


@bp.post("/device-check")
@require_interview_session
def device_check():
    interview = InterviewService().mark_device_checked(g.current_interview)
    return ok(serialize_interview_state(interview))


@bp.post("/start")
@require_interview_session
@limiter.limit("10 per hour")
def start_interview():
    service = InterviewService()
    try:
        interview = service.start(g.current_interview)
    except InterviewServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    current_question = service.get_current_question(interview)
    return ok(serialize_interview_state(interview, current_question=current_question))


@bp.get("/current-question")
@require_interview_session
def current_question():
    service = InterviewService()
    interview = g.current_interview
    question = service.get_current_question(interview)
    return ok(
        {
            "interview_status": interview.status,
            "current_round": interview.current_round,
            "question": serialize_question_public(question),
        }
    )


@bp.post("/answer")
@require_interview_session
@limiter.limit("60 per hour")
def submit_answer():
    try:
        payload = SubmitAnswerRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    parsed_question_id = _parse_uuid_or_none(payload.question_id)
    if parsed_question_id is None:
        return error("question_mismatch", "Invalid question id.", 409)

    service = InterviewService()
    try:
        interview = service.submit_answer(
            g.current_interview,
            question_id=parsed_question_id,
            transcript_text=payload.transcript_text,
        )
    except InterviewServiceError as exc:
        return error(exc.code, exc.message, exc.status_code)

    next_question = service.get_current_question(interview)
    return ok(serialize_interview_state(interview, current_question=next_question))


@bp.get("/report")
@require_interview_session
def get_my_report():
    """
    A student can view their own report through the same session used
    for the interview itself — no separate login exists for Institute
    Mode students (see README). If the session has expired by the time
    the report is ready (report generation is async and can lag behind
    interview completion), the student can no longer self-serve it —
    only their institute can retrieve it via the admin endpoint. A
    persistent student login is out of scope here; it belongs with
    Individual Mode.
    """
    interview = g.current_interview
    report = ReportRepository().get_by_interview(interview.id)
    if report is None or report.current_version is None:
        return error(
            "report_not_ready", "Your report hasn't been generated yet.", 404
        )
    return ok(serialize_report(report))


# ------------------------------------------------------------------
# Voice + Avatar (Phase 13)
# ------------------------------------------------------------------
MAX_AUDIO_UPLOAD_BYTES_BUFFER = 1024  # small buffer over the configured max, for early rejection


@bp.post("/transcribe")
@require_interview_session
@limiter.limit("30 per hour")
def transcribe_answer():
    """
    Speech-to-text step only — returns the transcript text, it does
    NOT submit an answer. The frontend takes this text and calls the
    existing POST /answer with it, same as if the student had typed
    it. Keeping these separate means the well-tested submit_answer
    flow (Phase 7) never needed to change for this phase.
    """
    if "file" not in request.files:
        return error("missing_file", "No audio was uploaded (expected field 'file').", 422)

    file = request.files["file"]
    if not file.filename:
        return error("missing_file", "No audio was uploaded.", 422)

    max_bytes = current_app.config["MAX_ANSWER_AUDIO_SIZE_BYTES"]
    data = file.read(max_bytes + MAX_AUDIO_UPLOAD_BYTES_BUFFER)
    if len(data) > max_bytes:
        return error("file_too_large", "Audio recording exceeds the maximum allowed size.", 422)

    from app.utils.file_validation import validate_upload

    try:
        content_type = validate_upload(
            data=data,
            max_size_bytes=max_bytes,
            allowed_content_types=("audio/webm", "audio/wav", "audio/mpeg", "audio/ogg"),
        )
    except FileValidationError as exc:
        return error("invalid_file", str(exc), 422)

    try:
        result = VoiceGateway().transcribe(audio_bytes=data, content_type=content_type)
    except VoiceProviderError as exc:
        return error("stt_unavailable", str(exc), 502)

    if not result.text:
        return error(
            "stt_not_configured",
            "Speech-to-text isn't set up for this institute yet. Please type your answer instead.",
            501,
        )

    return ok({"text": result.text, "source": result.source})


@bp.get("/question-audio")
@require_interview_session
@limiter.limit("60 per hour")
def get_question_audio():
    """
    TTS for the current question, as raw audio bytes. A 501 means no
    TTS provider is configured — the frontend's expected response is
    to fall back to the browser's own speechSynthesis API, not to
    treat this as a hard failure.
    """
    interview = g.current_interview
    service = InterviewService()
    question = service.get_current_question(interview)
    if question is None:
        return error("no_current_question", "There is no active question right now.", 409)

    campaign = CampaignRepository().get_by_id(
        interview.campaign_id, institute_id=interview.institute_id
    )
    voice_id = campaign.interviewer_voice if campaign else None

    try:
        result = VoiceGateway().synthesize(text=question.question_text, voice_id=voice_id)
    except VoiceProviderError as exc:
        return error("tts_unavailable", str(exc), 502)

    if result.audio_bytes is None:
        return error(
            "tts_not_configured",
            "Server-side text-to-speech isn't set up — use the browser's built-in voice instead.",
            501,
        )

    from flask import Response

    return Response(result.audio_bytes, mimetype=result.content_type or "audio/mpeg")


@bp.get("/avatar-session")
@require_interview_session
def get_avatar_session():
    """
    A 200 with provider="none" (not an error) means no avatar provider
    is configured — the frontend renders its static fallback
    illustration in that case. This is the expected default.
    """
    interview = g.current_interview
    campaign = CampaignRepository().get_by_id(
        interview.campaign_id, institute_id=interview.institute_id
    )
    avatar_id = campaign.interviewer_avatar if campaign else None

    try:
        session = VoiceGateway().create_avatar_session(avatar_id=avatar_id)
    except VoiceProviderError as exc:
        return error("avatar_unavailable", str(exc), 502)

    return ok(
        {
            "provider": session.provider,
            "embed_url": session.embed_url,
            "session_token": session.session_token,
        }
    )
