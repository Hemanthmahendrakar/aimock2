"""
Role + UserRole (many-to-many). Modeled this way — rather than a single
role column on User — so a user can hold multiple roles later (e.g. a
"Placement Officer" who is also "Institute Staff") without a migration.
"""
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class RoleName:
    PLATFORM_SUPER_ADMIN = "platform_super_admin"
    INSTITUTE_ADMIN = "institute_admin"
    STUDENT = "student"

    ALL = (PLATFORM_SUPER_ADMIN, INSTITUTE_ADMIN, STUDENT)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "roles"

    name = db.Column(db.String(64), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    """Join table between users and roles."""

    __tablename__ = "user_roles"

    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    role = db.relationship("Role")

    __table_args__ = (
        db.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
