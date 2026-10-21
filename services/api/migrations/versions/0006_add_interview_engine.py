"""add interview engine: interviews, interview_rounds, interview_questions, interview_answers

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("current_round", sa.String(16), nullable=True),
        sa.Column("access_token_hash", sa.String(64), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resume_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("device_checked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("technical_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("managerial_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("hr_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "campaign_id", "student_id", name="uq_interviews_campaign_student"
        ),
        sa.UniqueConstraint("access_token_hash", name="uq_interviews_access_token_hash"),
        sa.CheckConstraint(
            "status IN ('created', 'ready', 'in_progress', 'completed', 'evaluating', "
            "'report_generating', 'report_ready', 'failed', 'cancelled')",
            name="ck_interviews_status_valid",
        ),
    )
    op.create_index("ix_interviews_institute_id", "interviews", ["institute_id"])
    op.create_index("ix_interviews_campaign_id", "interviews", ["campaign_id"])
    op.create_index("ix_interviews_student_id", "interviews", ["student_id"])
    op.create_index(
        "ix_interviews_access_token_hash", "interviews", ["access_token_hash"]
    )

    op.create_table(
        "interview_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_type", sa.String(16), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "interview_id", "round_type", name="uq_interview_rounds_interview_round_type"
        ),
        sa.CheckConstraint(
            "round_type IN ('technical', 'managerial', 'hr')",
            name="ck_interview_rounds_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_interview_rounds_status_valid",
        ),
    )
    op.create_index(
        "ix_interview_rounds_interview_id", "interview_rounds", ["interview_id"]
    )

    op.create_table(
        "interview_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("interview_round_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_source", sa.String(64), nullable=False, server_default="heuristic_v1"),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "interview_round_id", "sequence_order",
            name="uq_interview_questions_round_sequence",
        ),
    )
    op.create_index(
        "ix_interview_questions_round_id", "interview_questions", ["interview_round_id"]
    )

    op.create_table(
        "interview_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("interview_question_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_taken_seconds", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "interview_question_id", name="uq_interview_answers_question_id"
        ),
    )


def downgrade():
    op.drop_table("interview_answers")
    op.drop_table("interview_questions")
    op.drop_table("interview_rounds")
    op.drop_table("interviews")
