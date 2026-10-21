"""
Authentication business logic. Routes call this; this calls
repositories. No Flask `request`/`response` objects are touched here
except reading config, so this stays unit-testable.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import current_app

from app.extensions import db
from app.models import (
    User,
    UserStatus,
    Institute,
    InstituteStatus,
    Role,
    RoleName,
    UserRole,
    RefreshToken,
    PasswordResetToken,
)
from app.repositories.user_repository import UserRepository
from app.repositories.institute_repository import InstituteRepository
from app.repositories.token_repository import TokenRepository
from app.services.audit_service import AuditService
from app.services.mail_service import MailService
from app.utils.security import generate_raw_token, hash_token, encode_jwt, decode_jwt


class AuthError(Exception):
    """Base class for auth failures. `code` maps to a stable API error code."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class EmailAlreadyRegistered(AuthError):
    def __init__(self):
        super().__init__("email_already_registered", "This email is already registered.", 409)


class InvalidCredentials(AuthError):
    def __init__(self):
        super().__init__("invalid_credentials", "Invalid email or password.", 401)


class AccountLocked(AuthError):
    def __init__(self):
        super().__init__(
            "account_locked",
            "This account is temporarily locked due to repeated failed logins.",
            423,
        )


class AccountNotActive(AuthError):
    def __init__(self, status: str):
        super().__init__(
            "account_not_active", f"Account is not active (status={status}).", 403
        )


class InvalidToken(AuthError):
    def __init__(self, what: str = "token"):
        super().__init__("invalid_token", f"This {what} is invalid or has expired.", 400)


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    refresh_token_expires_at: datetime


class AuthService:
    def __init__(self):
        self.users = UserRepository()
        self.institutes = InstituteRepository()
        self.tokens = TokenRepository()
        self.audit = AuditService()
        self.mail = MailService()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_institute(
        self,
        *,
        institute_name: str,
        institute_email: str,
        admin_full_name: str,
        admin_email: str,
        password: str,
    ) -> tuple[Institute, User]:
        """
        Registers a new institute together with its first admin user.
        institute_email and admin_email may differ (e.g. a generic
        "admissions@" address vs a named admin).
        """
        if self.institutes.email_exists(institute_email):
            raise EmailAlreadyRegistered()
        if self.users.email_exists(admin_email):
            raise EmailAlreadyRegistered()

        institute = Institute(
            name=institute_name,
            email=institute_email,
            status=InstituteStatus.ACTIVE,
        )
        self.institutes.create(institute)

        user = User(
            institute_id=institute.id,
            email=admin_email,
            full_name=admin_full_name,
            status=UserStatus.ACTIVE,
        )
        user.set_password(password)
        self.users.create(user)

        role = self._get_or_create_role(RoleName.INSTITUTE_ADMIN)
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.flush()

        self.audit.log(
            event_type="institute.registered",
            user_id=user.id,
            institute_id=institute.id,
            metadata={"institute_email": institute_email, "admin_email": admin_email},
        )

        db.session.commit()
        return institute, user

    def _get_or_create_role(self, name: str) -> Role:
        role = db.session.query(Role).filter(Role.name == name).first()
        if role is None:
            role = Role(name=name)
            db.session.add(role)
            db.session.flush()
        return role

    # ------------------------------------------------------------------
    # Login / logout / refresh
    # ------------------------------------------------------------------
    def login(self, *, email: str, password: str) -> tuple[User, TokenPair]:
        user = self.users.get_by_email(email)
        if user is None:
            # Constant-shape response: don't reveal whether the email exists.
            self.audit.log(event_type="auth.login_failed", metadata={"reason": "no_such_user"})
            raise InvalidCredentials()

        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            self.audit.log(
                event_type="auth.login_blocked_locked", user_id=user.id,
                institute_id=user.institute_id,
            )
            raise AccountLocked()

        if not user.verify_password(password):
            self._register_failed_login(user)
            db.session.commit()
            raise InvalidCredentials()

        # Email verification has been removed. Older accounts created by the
        # previous flow may still be pending verification; activate those after
        # successful password validation. Disabled accounts remain disabled.
        if user.status == UserStatus.PENDING_VERIFICATION:
            user.status = UserStatus.ACTIVE
            institute = (
                self.institutes.get_by_id(user.institute_id)
                if user.institute_id else None
            )
            if institute is not None and institute.status == InstituteStatus.PENDING:
                institute.status = InstituteStatus.ACTIVE

        if user.status != UserStatus.ACTIVE:
            self.audit.log(
                event_type="auth.login_blocked_inactive", user_id=user.id,
                institute_id=user.institute_id, metadata={"status": user.status},
            )
            db.session.commit()
            raise AccountNotActive(user.status)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)

        token_pair = self._issue_token_pair(user)

        self.audit.log(
            event_type="auth.login_succeeded", user_id=user.id, institute_id=user.institute_id
        )
        db.session.commit()
        return user, token_pair

    def _register_failed_login(self, user: User) -> None:
        user.failed_login_attempts += 1
        self.audit.log(
            event_type="auth.login_failed",
            user_id=user.id,
            institute_id=user.institute_id,
            metadata={"attempts": user.failed_login_attempts},
        )
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )
            self.audit.log(
                event_type="auth.account_locked", user_id=user.id, institute_id=user.institute_id
            )

    def _issue_token_pair(self, user: User) -> TokenPair:
        access_token = encode_jwt(
            secret_key=current_app.config["SECRET_KEY"],
            algorithm=current_app.config["JWT_ALGORITHM"],
            subject=str(user.id),
            ttl=current_app.config["JWT_ACCESS_TOKEN_TTL"],
            extra_claims={
                "institute_id": str(user.institute_id) if user.institute_id else None,
                "roles": user.role_names,
            },
        )

        raw_refresh = generate_raw_token()
        expires_at = datetime.now(timezone.utc) + current_app.config["JWT_REFRESH_TOKEN_TTL"]
        refresh_row = RefreshToken(
            user_id=user.id, token_hash=hash_token(raw_refresh), expires_at=expires_at
        )
        self.tokens.create_refresh_token(refresh_row)

        return TokenPair(
            access_token=access_token,
            refresh_token=raw_refresh,
            refresh_token_expires_at=expires_at,
        )

    def refresh_access_token(self, raw_refresh_token: str) -> tuple[User, TokenPair]:
        row = self.tokens.get_refresh_token_by_hash(hash_token(raw_refresh_token))
        if row is None or not row.is_active:
            raise InvalidToken("refresh token")

        user = self.users.get_by_id(row.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidToken("refresh token")

        # Rotate: revoke the old refresh token, issue a new pair.
        self.tokens.revoke_refresh_token(row)
        token_pair = self._issue_token_pair(user)

        self.audit.log(
            event_type="auth.token_refreshed", user_id=user.id, institute_id=user.institute_id
        )
        db.session.commit()
        return user, token_pair

    def logout(self, raw_refresh_token: Optional[str]) -> None:
        if not raw_refresh_token:
            return
        row = self.tokens.get_refresh_token_by_hash(hash_token(raw_refresh_token))
        if row is not None and row.is_active:
            self.tokens.revoke_refresh_token(row)
            self.audit.log(
                event_type="auth.logout", user_id=row.user_id
            )
            db.session.commit()

    def decode_access_token(self, access_token: str) -> dict:
        try:
            return decode_jwt(
                token=access_token,
                secret_key=current_app.config["SECRET_KEY"],
                algorithm=current_app.config["JWT_ALGORITHM"],
            )
        except Exception:
            raise InvalidToken("access token")

    # ------------------------------------------------------------------
    # Forgot / reset password
    # ------------------------------------------------------------------
    def request_password_reset(self, email: str) -> None:
        user = self.users.get_by_email(email)
        if user is None:
            # Do not reveal account existence; just no-op quietly.
            return

        raw_token = generate_raw_token()
        token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + current_app.config["PASSWORD_RESET_TTL"],
        )
        self.tokens.create_password_reset_token(token)

        reset_link = (
            f"{current_app.config['FRONTEND_ORIGIN']}"
            f"/institute/reset-password?token={raw_token}"
        )
        self.mail.send_password_reset(to_email=user.email, reset_link=reset_link)

        self.audit.log(
            event_type="auth.password_reset_requested",
            user_id=user.id,
            institute_id=user.institute_id,
        )
        db.session.commit()

    def reset_password(self, *, raw_token: str, new_password: str) -> User:
        token = self.tokens.get_password_reset_token_by_hash(hash_token(raw_token))
        if token is None or token.used_at is not None:
            raise InvalidToken("password reset link")
        if token.expires_at < datetime.now(timezone.utc):
            raise InvalidToken("password reset link")

        user = self.users.get_by_id(token.user_id)
        if user is None:
            raise InvalidToken("password reset link")

        user.set_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        token.used_at = datetime.now(timezone.utc)

        # Reset compromises any existing sessions.
        self.tokens.revoke_all_for_user(user.id)

        self.audit.log(
            event_type="auth.password_reset_completed",
            user_id=user.id,
            institute_id=user.institute_id,
        )
        db.session.commit()
        return user
