"""add interview templates/rounds, link campaigns

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interview_templates",
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
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint(
            "institute_id", "name", name="uq_interview_templates_institute_name"
        ),
    )
    op.create_index(
        "ix_interview_templates_institute_id", "interview_templates", ["institute_id"]
    )

    op.create_table(
        "interview_template_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("template_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("interview_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_type", sa.String(16), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("question_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("evaluation_criteria", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "template_id", "round_type", name="uq_template_rounds_template_round_type"
        ),
        sa.CheckConstraint(
            "round_type IN ('technical', 'managerial', 'hr')",
            name="ck_template_rounds_type_valid",
        ),
        sa.CheckConstraint(
            "duration_minutes > 0", name="ck_template_rounds_duration_positive"
        ),
    )
    op.create_index(
        "ix_template_rounds_template_id", "interview_template_rounds", ["template_id"]
    )

    op.add_column(
        "campaigns",
        sa.Column(
            "interview_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_campaigns_interview_template_id", "campaigns", ["interview_template_id"]
    )
    op.add_column("campaigns", sa.Column("technical_instructions", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("managerial_instructions", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("hr_instructions", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("campaigns", "hr_instructions")
    op.drop_column("campaigns", "managerial_instructions")
    op.drop_column("campaigns", "technical_instructions")
    op.drop_index("ix_campaigns_interview_template_id", table_name="campaigns")
    op.drop_column("campaigns", "interview_template_id")
    op.drop_table("interview_template_rounds")
    op.drop_table("interview_templates")
