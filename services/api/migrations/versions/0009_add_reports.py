"""add reports table

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    # reports is created WITHOUT current_version_id's FK constraint —
    # report_versions doesn't exist yet. Added via ALTER after
    # report_versions is created, same circular-FK resolution as
    # resumes/resume_versions in migration 0005.
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("interview_id", name="uq_reports_interview_id"),
    )
    op.create_index("ix_reports_institute_id", "reports", ["institute_id"])

    op.create_table(
        "report_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("report_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=False),
        sa.Column("communication_score", sa.Integer(), nullable=False),
        sa.Column("managerial_score", sa.Integer(), nullable=False),
        sa.Column("hr_score", sa.Integer(), nullable=False),
        sa.Column("problem_solving_score", sa.Integer(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("weaknesses", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("technical_skill_gaps", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("communication_improvements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("interview_highlights", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recommended_preparation", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("improvement_plan", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False,
                   server_default="report_prompt_v1"),
        sa.Column("evaluation_version", sa.String(32), nullable=False),
        sa.Column("report_source", sa.String(64), nullable=False, server_default="heuristic_v1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "report_id", "version_number", name="uq_report_versions_report_version"
        ),
        sa.CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100",
            name="ck_report_versions_overall_range",
        ),
    )
    op.create_index("ix_report_versions_report_id", "report_versions", ["report_id"])

    op.add_column(
        "reports",
        sa.Column(
            "current_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_reports_current_version_id",
        "reports",
        "report_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "interviews", sa.Column("report_generated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("interviews", sa.Column("report_generation_error", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("interviews", "report_generation_error")
    op.drop_column("interviews", "report_generated_at")
    op.drop_constraint("fk_reports_current_version_id", "reports", type_="foreignkey")
    op.drop_column("reports", "current_version_id")
    op.drop_table("report_versions")
    op.drop_table("reports")
