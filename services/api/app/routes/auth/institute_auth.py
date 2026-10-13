"""
Institute authentication routes. Handlers stay thin: parse/validate
input, call AuthService, translate the result/exception into a
response. All business logic lives in AuthService.
"""
from flask import Blueprint, request, g
from pydantic import ValidationError

from app.extensions import limiter
from app.schemas.auth_schemas import (
    RegisterInstituteRequest,
    LoginRequest,
    VerifyEmailRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.services.auth_service import AuthService, AuthError
from app.utils.authorization import require_auth
from app.utils.responses import ok, error

bp = Blueprint("institute_auth", __name__, url_prefix="/api/v1/institute/auth")


def _validation_error_response(exc: ValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return error("validation_error", "Invalid request data.", 422, details=details)


def _set_auth_cookies(response, token_pair):
    from flask import current_app

    max_age_access = int(current_app.config["JWT_ACCESS_TOKEN_TTL"].total_seconds())
    max_age_refresh = int(current_app.config["JWT_REFRESH_TOKEN_TTL"].total_seconds())

    response.set_cookie(
        current_app.config["ACCESS_COOKIE_NAME"],
        token_pair.access_token,
        max_age=max_age_access,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite=current_app.config["COOKIE_SAMESITE"],
        domain=current_app.config["COOKIE_DOMAIN"],
        path="/",
    )
    response.set_cookie(
        current_app.config["REFRESH_COOKIE_NAME"],
        token_pair.refresh_token,
        max_age=max_age_refresh,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite=current_app.config["COOKIE_SAMESITE"],
        domain=current_app.config["COOKIE_DOMAIN"],
        path="/api/v1/institute/auth",
    )
    return response


def _clear_auth_cookies(response):
    from flask import current_app

    response.delete_cookie(current_app.config["ACCESS_COOKIE_NAME"], path="/")
    response.delete_cookie(
        current_app.config["REFRESH_COOKIE_NAME"], path="/api/v1/institute/auth"
    )
    return response


@bp.post("/register")
@limiter.limit("5 per hour")
def register():
    try:
        payload = RegisterInstituteRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = AuthService()
    try:
        institute, user = service.register_institute(
            institute_name=payload.institute_name,
            institute_email=payload.institute_email,
            admin_full_name=payload.admin_full_name,
            admin_email=payload.admin_email,
            password=payload.password,
        )
    except AuthError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok(
        {
            "institute": {"id": str(institute.id), "name": institute.name},
            "user": {"id": str(user.id), "email": user.email, "status": user.status},
            "message": "Registration successful. Check your email to verify your account.",
        },
        status=201,
    )


@bp.post("/verify-email")
@limiter.limit("10 per hour")
def verify_email():
    try:
        payload = VerifyEmailRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = AuthService()
    try:
        user = service.verify_email(payload.token)
    except AuthError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok({"user": {"id": str(user.id), "email": user.email, "status": user.status}})


@bp.post("/login")
@limiter.limit("10 per 15 minutes")
def login():
    try:
        payload = LoginRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = AuthService()
    try:
        user, token_pair = service.login(email=payload.email, password=payload.password)
    except AuthError as exc:
        return error(exc.code, exc.message, exc.status_code)

    response, status = ok(
        {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "institute_id": str(user.institute_id) if user.institute_id else None,
                "roles": user.role_names,
            }
        }
    )
    return _set_auth_cookies(response, token_pair), status


@bp.post("/refresh")
@limiter.limit("30 per hour")
def refresh():
    from flask import current_app

    raw_refresh_token = request.cookies.get(current_app.config["REFRESH_COOKIE_NAME"])
    if not raw_refresh_token:
        return error("unauthenticated", "No refresh token provided.", 401)

    service = AuthService()
    try:
        user, token_pair = service.refresh_access_token(raw_refresh_token)
    except AuthError as exc:
        return error(exc.code, exc.message, exc.status_code)

    response, status = ok({"user": {"id": str(user.id)}})
    return _set_auth_cookies(response, token_pair), status


@bp.post("/logout")
def logout():
    from flask import current_app

    raw_refresh_token = request.cookies.get(current_app.config["REFRESH_COOKIE_NAME"])
    AuthService().logout(raw_refresh_token)

    response, status = ok({"message": "Logged out."})
    return _clear_auth_cookies(response), status


@bp.post("/forgot-password")
@limiter.limit("5 per hour")
def forgot_password():
    try:
        payload = ForgotPasswordRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    AuthService().request_password_reset(payload.email)
    # Always return the same message, regardless of whether the email
    # exists, so this endpoint can't be used to enumerate accounts.
    return ok({"message": "If that email is registered, a reset link has been sent."})


@bp.post("/reset-password")
@limiter.limit("10 per hour")
def reset_password():
    try:
        payload = ResetPasswordRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as exc:
        return _validation_error_response(exc)

    service = AuthService()
    try:
        user = service.reset_password(raw_token=payload.token, new_password=payload.new_password)
    except AuthError as exc:
        return error(exc.code, exc.message, exc.status_code)

    return ok({"user": {"id": str(user.id)}, "message": "Password has been reset."})


@bp.get("/me")
@require_auth
def me():
    user = g.current_user
    return ok(
        {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
            "institute_id": str(user.institute_id) if user.institute_id else None,
            "roles": user.role_names,
            "email_verified": user.email_verified_at is not None,
        }
    )
