from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin

class QuestionBankQuestion(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "question_bank_questions"
    institute_id = db.Column(UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    question = db.Column(db.Text, nullable=False)
    expected_answer_criteria = db.Column(db.Text, nullable=True)
    role = db.Column(db.String(180), nullable=True)
    round_type = db.Column(db.String(32), nullable=False, default="technical")
    category = db.Column(db.String(120), nullable=True)
    difficulty = db.Column(db.String(16), nullable=False, default="medium")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (db.CheckConstraint("round_type IN ('technical','managerial','hr')", name="ck_question_bank_round_type"), db.CheckConstraint("difficulty IN ('easy','medium','hard')", name="ck_question_bank_difficulty"), db.Index("ix_question_bank_institute_round", "institute_id", "round_type"))
