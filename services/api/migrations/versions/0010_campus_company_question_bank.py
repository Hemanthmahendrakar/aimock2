"""Add campuses, company catalog, and institute question bank.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("campuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False), sa.Column("code", sa.String(64)), sa.Column("location", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("institute_id", "name", name="uq_campuses_institute_name"), sa.UniqueConstraint("institute_id", "code", name="uq_campuses_institute_code"))
    op.create_index("ix_campuses_institute_id", "campuses", ["institute_id"])
    op.create_table("companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=True), sa.Column("name", sa.String(180), nullable=False), sa.Column("website", sa.String(255)), sa.Column("description", sa.Text()), sa.UniqueConstraint("institute_id", "name", name="uq_companies_institute_name"))
    op.create_index("ix_companies_institute_id", "companies", ["institute_id"]); op.create_index("ix_companies_name", "companies", ["name"])
    op.create_table("question_bank_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("institute_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("question", sa.Text(), nullable=False), sa.Column("expected_answer_criteria", sa.Text()), sa.Column("role", sa.String(180)), sa.Column("round_type", sa.String(32), nullable=False, server_default="technical"), sa.Column("category", sa.String(120)), sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("round_type IN ('technical','managerial','hr')", name="ck_question_bank_round_type"), sa.CheckConstraint("difficulty IN ('easy','medium','hard')", name="ck_question_bank_difficulty"))
    op.create_index("ix_question_bank_questions_institute_id", "question_bank_questions", ["institute_id"]); op.create_index("ix_question_bank_questions_company_id", "question_bank_questions", ["company_id"]); op.create_index("ix_question_bank_institute_round", "question_bank_questions", ["institute_id", "round_type"])
    # Optional student attributes preserve compatibility with existing rows.
    op.add_column("students", sa.Column("campus_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True))
    op.add_column("students", sa.Column("course", sa.String(180), nullable=True)); op.add_column("students", sa.Column("graduation_year", sa.Integer(), nullable=True)); op.add_column("students", sa.Column("experience_level", sa.String(64), nullable=True))
    op.create_index("ix_students_campus_id", "students", ["campus_id"])
    op.add_column("campaigns", sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True))
    op.add_column("campaigns", sa.Column("campus_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True))
    op.add_column("campaigns", sa.Column("job_description", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("question_source", sa.String(16), nullable=False, server_default="ai"))
    op.create_check_constraint("ck_campaigns_question_source_valid", "campaigns", "question_source IN ('ai','custom','mixed')")
    op.create_index("ix_campaigns_company_id", "campaigns", ["company_id"]); op.create_index("ix_campaigns_campus_id", "campaigns", ["campus_id"])

def downgrade():
    op.drop_index("ix_campaigns_campus_id", table_name="campaigns"); op.drop_index("ix_campaigns_company_id", table_name="campaigns")
    op.drop_constraint("ck_campaigns_question_source_valid", "campaigns", type_="check"); op.drop_column("campaigns", "question_source"); op.drop_column("campaigns", "job_description"); op.drop_column("campaigns", "campus_id"); op.drop_column("campaigns", "company_id")
    op.drop_index("ix_students_campus_id", table_name="students"); op.drop_column("students", "experience_level"); op.drop_column("students", "graduation_year"); op.drop_column("students", "course"); op.drop_column("students", "campus_id")
    op.drop_index("ix_question_bank_institute_round", table_name="question_bank_questions"); op.drop_index("ix_question_bank_questions_company_id", table_name="question_bank_questions"); op.drop_index("ix_question_bank_questions_institute_id", table_name="question_bank_questions"); op.drop_table("question_bank_questions")
    op.drop_index("ix_companies_name", table_name="companies"); op.drop_index("ix_companies_institute_id", table_name="companies"); op.drop_table("companies")
    op.drop_index("ix_campuses_institute_id", table_name="campuses"); op.drop_table("campuses")
