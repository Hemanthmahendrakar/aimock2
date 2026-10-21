from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin

class Company(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "companies"
    # Null institute_id denotes a shared catalog entry; institute-owned entries are tenant-scoped.
    institute_id = db.Column(UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=True, index=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    website = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    __table_args__ = (db.UniqueConstraint("institute_id", "name", name="uq_companies_institute_name"),)
