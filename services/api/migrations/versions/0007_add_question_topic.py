"""add topic column to interview_questions

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "interview_questions", sa.Column("topic", sa.String(64), nullable=True)
    )


def downgrade():
    op.drop_column("interview_questions", "topic")
