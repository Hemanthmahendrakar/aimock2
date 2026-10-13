"""
Audit log — append-only record of security-relevant events
(registration, login success/failure, password reset, etc).
Never log secrets (passwords, tokens) into this table.
"""
from sqlalchemy.dialects.postgresql import UUID, INET

from app.extensions import db
from app.models.base import UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, db.Model):
    __tablename__ = "audit_logs"

    # Nullable: some events (e.g. failed login with unknown email) have
    # no resolvable user_id.
    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    institute_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="SET NULL"), nullable=True, index=True
    )

    event_type = db.Column(db.String(64), nullable=False, index=True)
    # Non-sensitive structured context, e.g. {"reason": "invalid_password"}
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)

    ip_address = db.Column(INET, nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True
    )
