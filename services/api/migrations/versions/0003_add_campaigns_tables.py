"""add campaigns and campaign_students tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(255), nullable=False),
        sa.Column("experience_level", sa.String(64), nullable=True),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("batch", sa.String(32), nullable=True),
        sa.Column("technical_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("managerial_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("hr_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("interviewer_avatar", sa.String(128), nullable=True),
        sa.Column("interviewer_voice", sa.String(128), nullable=True),
        sa.Column("interview_style", sa.String(64), nullable=True),
        sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("question_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("evaluation_criteria", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'archived')",
            name="ck_campaigns_status_valid",
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')", name="ck_campaigns_difficulty_valid"
        ),
        sa.CheckConstraint(
            "technical_duration_minutes > 0", name="ck_campaigns_tech_duration_positive"
        ),
        sa.CheckConstraint(
            "managerial_duration_minutes > 0", name="ck_campaigns_mgr_duration_positive"
        ),
        sa.CheckConstraint("hr_duration_minutes > 0", name="ck_campaigns_hr_duration_positive"),
    )
    op.create_index("ix_campaigns_institute_id", "campaigns", ["institute_id"])
    op.create_index(
        "ix_campaigns_institute_status", "campaigns", ["institute_id", "status"]
    )

    op.create_table(
        "campaign_students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint(
            "campaign_id", "student_id", name="uq_campaign_students_campaign_student"
        ),
    )
    op.create_index(
        "ix_campaign_students_campaign_id", "campaign_students", ["campaign_id"]
    )
    op.create_index(
        "ix_campaign_students_student_id", "campaign_students", ["student_id"]
    )


def downgrade():
    op.drop_table("campaign_students")
    op.drop_table("campaigns")
