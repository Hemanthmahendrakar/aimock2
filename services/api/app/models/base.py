"""
Base model mixins shared across all tables.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = _utcnow()


class UUIDPrimaryKeyMixin:
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
