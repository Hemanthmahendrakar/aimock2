"""add resumes, resume_versions, candidate_profiles

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # resumes is created WITHOUT current_version_id's FK constraint —
    # resume_versions doesn't exist yet. The column + FK are added via
    # ALTER after resume_versions is created, resolving the circular
    # reference (resumes.current_version_id -> resume_versions.id,
    # resume_versions.resume_id -> resumes.id).
    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("student_id", name="uq_resumes_student_id"),
    )
    op.create_index("ix_resumes_institute_id", "resumes", ["institute_id"])

    op.create_table(
        "resume_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("extraction_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "resume_id", "version_number", name="uq_resume_versions_resume_version"
        ),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_resume_versions_extraction_status_valid",
        ),
    )
    op.create_index("ix_resume_versions_resume_id", "resume_versions", ["resume_id"])
    op.create_index("ix_resume_versions_institute_id", "resume_versions", ["institute_id"])

    op.add_column(
        "resumes",
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_resumes_current_version_id",
        "resumes",
        "resume_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "candidate_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("resume_version_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("education", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("programming_languages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("technologies", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("projects", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("internships", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("experience", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("certifications", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("achievements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("extraction_method", sa.String(64), nullable=True),
        sa.Column("analysis_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "resume_version_id", name="uq_candidate_profiles_resume_version_id"
        ),
        sa.CheckConstraint(
            "analysis_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_candidate_profiles_analysis_status_valid",
        ),
    )


def downgrade():
    op.drop_table("candidate_profiles")
    op.drop_constraint("fk_resumes_current_version_id", "resumes", type_="foreignkey")
    op.drop_column("resumes", "current_version_id")
    op.drop_table("resume_versions")
    op.drop_table("resumes")
