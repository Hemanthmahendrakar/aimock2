"""add evaluations table

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension", sa.String(16), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("criteria_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("strengths", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("weaknesses", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("improvement_suggestions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("evaluation_source", sa.String(64), nullable=False,
                   server_default="heuristic_v1"),
        sa.CheckConstraint(
            "dimension IN ('technical', 'managerial', 'hr', 'communication')",
            name="ck_evaluations_dimension_valid",
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_evaluations_score_range"),
        sa.UniqueConstraint(
            "interview_id", "dimension", name="uq_evaluations_interview_dimension"
        ),
    )
    op.create_index("ix_evaluations_interview_id", "evaluations", ["interview_id"])

    op.add_column("interviews", sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interviews", sa.Column("evaluation_error", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("interviews", "evaluation_error")
    op.drop_column("interviews", "evaluated_at")
    op.drop_table("evaluations")
