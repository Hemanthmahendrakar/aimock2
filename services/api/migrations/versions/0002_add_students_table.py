"""add students table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("roll_number", sa.String(64), nullable=True),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("batch", sa.String(32), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_students_status_valid"),
        sa.UniqueConstraint("institute_id", "email", name="uq_students_institute_email"),
        sa.UniqueConstraint(
            "institute_id", "roll_number", name="uq_students_institute_roll_number"
        ),
    )
    op.create_index("ix_students_institute_id", "students", ["institute_id"])
    op.create_index(
        "ix_students_institute_department", "students", ["institute_id", "department"]
    )
    op.create_index("ix_students_institute_batch", "students", ["institute_id", "batch"])


def downgrade():
    op.drop_table("students")
