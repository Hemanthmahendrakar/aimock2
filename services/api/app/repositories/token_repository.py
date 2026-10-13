"""
Repository for the three token tables. Tokens are looked up by hash
(never by raw value — the raw value never touches the DB).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models import RefreshToken, EmailVerificationToken, PasswordResetToken


class TokenRepository:
    # --- refresh tokens --------------------------------------------------
    def create_refresh_token(self, token: RefreshToken) -> RefreshToken:
        db.session.add(token)
        db.session.flush()
        return token

    def get_refresh_token_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        return (
            db.session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def revoke_refresh_token(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        db.session.add(token)

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        (
            db.session.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .update({"revoked_at": datetime.now(timezone.utc)})
        )

    # --- email verification ----------------------------------------------
    def create_email_verification_token(
        self, token: EmailVerificationToken
    ) -> EmailVerificationToken:
        db.session.add(token)
        db.session.flush()
        return token

    def get_email_verification_token_by_hash(
        self, token_hash: str
    ) -> Optional[EmailVerificationToken]:
        return (
            db.session.query(EmailVerificationToken)
            .filter(EmailVerificationToken.token_hash == token_hash)
            .first()
        )

    # --- password reset -----------------------------------------------
    def create_password_reset_token(self, token: PasswordResetToken) -> PasswordResetToken:
        db.session.add(token)
        db.session.flush()
        return token

    def get_password_reset_token_by_hash(
        self, token_hash: str
    ) -> Optional[PasswordResetToken]:
        return (
            db.session.query(PasswordResetToken)
            .filter(PasswordResetToken.token_hash == token_hash)
            .first()
        )
