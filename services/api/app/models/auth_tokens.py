"""
Auth-related token tables.

Design note: we never store raw tokens. Each table stores a SHA-256
hash of the token; the raw token is only ever sent to the client
(cookie or email link) and never persisted. This means a DB leak does
not leak usable tokens, and revocation is a simple row update/delete.
"""
from sqlalchemy.dialects.postgresql import UUID, INET

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "refresh_tokens"

    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    ip_address = db.Column(INET, nullable=True)

    @property
    def is_active(self) -> bool:
        from datetime import datetime, timezone

        return self.revoked_at is None and self.expires_at > datetime.now(timezone.utc)


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "password_reset_tokens"

    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
