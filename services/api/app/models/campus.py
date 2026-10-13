from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin

class Campus(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "campuses"
    institute_id = db.Column(UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    code = db.Column(db.String(64), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (db.UniqueConstraint("institute_id", "name", name="uq_campuses_institute_name"), db.UniqueConstraint("institute_id", "code", name="uq_campuses_institute_code"))
