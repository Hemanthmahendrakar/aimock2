"""
Authorization decorators.

CRITICAL RULE: institute_id for the current request is derived ONLY
from `g.current_user` (populated from the verified access token). It
is never read from the request body, query string, or URL path. Any
route that needs "the current institute" must call
`g.current_user.institute_id` — this file is the single place that
trust boundary is established.
"""
import functools
import uuid
from typing import Callable

from flask import g, request, current_app

from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService, InvalidToken
from app.utils.responses import error


def _extract_access_token() -> str | None:
    # Prefer the httpOnly cookie; fall back to Authorization header for
    # non-browser clients (mobile apps, tests, service-to-service calls).
    token = request.cookies.get(current_app.config["ACCESS_COOKIE_NAME"])
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :]
    return None


def require_auth(view_func: Callable) -> Callable:
    """Populates g.current_user / g.current_user_claims, or returns 401."""

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        token = _extract_access_token()
        if not token:
            return error("unauthenticated", "Authentication required.", 401)

        auth_service = AuthService()
        try:
            claims = auth_service.decode_access_token(token)
        except InvalidToken:
            return error("unauthenticated", "Invalid or expired session.", 401)

        try:
            user_id = uuid.UUID(claims["sub"])
        except (KeyError, ValueError, TypeError):
            return error("unauthenticated", "Invalid or expired session.", 401)
        user = UserRepository().get_by_id(user_id)
        if user is None or user.deleted_at is not None:
            return error("unauthenticated", "Invalid or expired session.", 401)
        if user.status != "active":
            return error("account_not_active", "Account is not active.", 403)

        g.current_user = user
        g.current_user_claims = claims
        return view_func(*args, **kwargs)

    return wrapper


def require_role(*allowed_roles: str) -> Callable:
    """Must be used AFTER require_auth (or combined via require_auth_and_role)."""

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return error("unauthenticated", "Authentication required.", 401)
            if not any(user.has_role(r) for r in allowed_roles):
                return error("forbidden", "You do not have access to this resource.", 403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def require_institute_scope(view_func: Callable) -> Callable:
    """
    Guarantees the current user belongs to an institute before entering
    an institute-scoped route (blocks platform-admin-only or
    student-without-institute users from institute-admin endpoints).
    Downstream code must read `g.current_user.institute_id` — never a
    client-supplied institute_id — to scope queries.
    """

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if user is None:
            return error("unauthenticated", "Authentication required.", 401)
        if user.institute_id is None:
            return error(
                "forbidden", "This action requires an institute-scoped account.", 403
            )
        g.current_institute_id = user.institute_id
        return view_func(*args, **kwargs)

    return wrapper


def require_interview_session(view_func: Callable) -> Callable:
    """
    Authenticates a student's interview session — a completely
    separate trust boundary from require_auth/institute admins. The
    session JWT is issued only after a valid interview access token is
    exchanged (see InterviewService.exchange_access_token) and is
    scoped to exactly one interview via its 'interview_id' claim; nulls
    out g.current_user so institute-admin-oriented code never
    accidentally treats a student session as an admin one.
    """

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        from app.services.interview_service import InterviewService, InterviewNotFound

        token = request.cookies.get(current_app.config["INTERVIEW_SESSION_COOKIE_NAME"])
        if not token:
            return error("unauthenticated", "Interview session required.", 401)

        try:
            claims = jwt_decode_interview_session(token)
        except Exception:
            return error("unauthenticated", "Invalid or expired interview session.", 401)

        try:
            interview_id = uuid.UUID(claims["interview_id"])
        except (KeyError, ValueError, TypeError):
            return error("unauthenticated", "Invalid or expired interview session.", 401)

        try:
            interview = InterviewService().get_by_id_for_session(interview_id)
        except InterviewNotFound:
            return error("unauthenticated", "Invalid or expired interview session.", 401)

        g.current_interview = interview
        return view_func(*args, **kwargs)

    return wrapper


def jwt_decode_interview_session(token: str) -> dict:
    from app.utils.security import decode_jwt

    return decode_jwt(
        token=token,
        secret_key=current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )
