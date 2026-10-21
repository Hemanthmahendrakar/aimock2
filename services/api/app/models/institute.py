"""
Institute — the tenant entity. Every piece of institute-scoped data
(students, campaigns, interviews, reports, ...) carries an institute_id
that traces back here.
"""
from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class InstituteStatus:
    PENDING = "pending"          # legacy status retained for existing database rows
    ACTIVE = "active"
    SUSPENDED = "suspended"

    ALL = (PENDING, ACTIVE, SUSPENDED)


class BrandingField:
    """Keys used inside Institute.branding_config (a JSON column, kept
    schema-flexible on purpose — new branding fields don't need a
    migration, they just need a new key here and validation in the
    schema)."""

    PRIMARY_COLOR = "primary_color"
    SECONDARY_COLOR = "secondary_color"


class Institute(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "institutes"

    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.Text, nullable=True)
    website = db.Column(db.String(255), nullable=True)

    # NOTE: despite the column name (kept from Phase 1 to avoid a
    # migration), this stores the S3 OBJECT KEY, not a public URL. The
    # bucket is private; callers get a short-lived signed URL via
    # FileStorageService at read time. See InstituteService.get_profile.
    logo_url = db.Column(db.String(1024), nullable=True)

    # Free-form JSON for theme colors, custom domain, etc. Kept flexible
    # on purpose — branding needs will grow without new columns/migrations.
    branding_config = db.Column(db.JSON, nullable=False, default=dict)

    status = db.Column(
        db.String(32), nullable=False, default=InstituteStatus.ACTIVE
    )

    users = db.relationship("User", back_populates="institute", lazy="dynamic")

    __table_args__ = (
        db.CheckConstraint(
            f"status IN {InstituteStatus.ALL}", name="ck_institutes_status_valid"
        ),
    )

    def __repr__(self) -> str:
        return f"<Institute {self.id} {self.name!r}>"
