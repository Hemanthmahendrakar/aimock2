"""
Student — a managed record within an institute (Institute Mode). This
is deliberately NOT a login account: students don't authenticate in
Phase 3. Login is introduced later, scoped to interview assignment
(Phase 7), and will likely add a nullable user_id link here rather
than duplicating this table.

institute_id is nullable — mirroring User — so a future Individual
Mode (self-registered students with no institute) can reuse this
table without a migration. Every Phase 3 code path still requires it
to be set; that's enforced in StudentService, not at the DB level.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


class StudentStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"

    ALL = (ACTIVE, INACTIVE)


class Student(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "students"

    institute_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    roll_number = db.Column(db.String(64), nullable=True)
    department = db.Column(db.String(128), nullable=True)
    batch = db.Column(db.String(32), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    campus_id = db.Column(UUID(as_uuid=True), db.ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True)
    course = db.Column(db.String(180), nullable=True)
    graduation_year = db.Column(db.Integer, nullable=True)
    experience_level = db.Column(db.String(64), nullable=True)

    status = db.Column(db.String(32), nullable=False, default=StudentStatus.ACTIVE)

    __table_args__ = (
        db.CheckConstraint(f"status IN {StudentStatus.ALL}", name="ck_students_status_valid"),
        db.UniqueConstraint("institute_id", "email", name="uq_students_institute_email"),
        db.UniqueConstraint(
            "institute_id", "roll_number", name="uq_students_institute_roll_number"
        ),
        db.Index("ix_students_institute_department", "institute_id", "department"),
        db.Index("ix_students_institute_batch", "institute_id", "batch"),
    )

    def __repr__(self) -> str:
        return f"<Student {self.id} {self.email!r}>"
