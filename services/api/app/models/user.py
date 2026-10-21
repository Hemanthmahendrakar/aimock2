"""
User model. institute_id is nullable so that:
  - platform_super_admin users (no institute)
  - future individual-mode students (no institute)
can exist in the same table without hacks. Institute-scoped users
(institute_admin, and later institute_staff/placement_officer) always
have institute_id set, and that is enforced at the service layer.
"""
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin

_hasher = PasswordHasher()


class UserStatus:
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    DISABLED = "disabled"

    ALL = (PENDING_VERIFICATION, ACTIVE, DISABLED)


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "users"

    institute_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    full_name = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(32), nullable=False, default=UserStatus.ACTIVE)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)

    institute = db.relationship("Institute", back_populates="users")
    user_roles = db.relationship(
        "UserRole", backref="user", cascade="all, delete-orphan", lazy="joined"
    )

    __table_args__ = (
        db.CheckConstraint(f"status IN {UserStatus.ALL}", name="ck_users_status_valid"),
    )

    # --- password handling -------------------------------------------------
    def set_password(self, plaintext: str) -> None:
        self.password_hash = _hasher.hash(plaintext)

    def verify_password(self, plaintext: str) -> bool:
        try:
            valid = _hasher.verify(self.password_hash, plaintext)
        except (VerifyMismatchError, VerificationError, InvalidHash):
            return False
        if valid and _hasher.check_needs_rehash(self.password_hash):
            # Transparently upgrade the hash if Argon2 parameters changed.
            self.password_hash = _hasher.hash(plaintext)
        return valid

    # --- role helpers --------------------------------------------------
    @property
    def role_names(self) -> list[str]:
        return [ur.role.name for ur in self.user_roles]

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email!r}>"
