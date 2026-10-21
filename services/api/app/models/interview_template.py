"""
InterviewTemplate — a reusable, institute-owned preset for interview
round configuration, built once and applied to many campaigns (see
CampaignService.apply_template). This is deliberately separate from
Campaign's own round fields (added in Phase 4): applying a template
COPIES its round config onto a campaign at that moment, it does not
create a live link — editing a template later must never reshape a
campaign that already applied it.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


class InterviewRoundType:
    TECHNICAL = "technical"
    MANAGERIAL = "managerial"
    HR = "hr"

    ALL = (TECHNICAL, MANAGERIAL, HR)


class InterviewTemplate(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "interview_templates"

    institute_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    rounds = db.relationship(
        "InterviewTemplateRound",
        backref="template",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="InterviewTemplateRound.sequence_order",
    )

    __table_args__ = (
        db.UniqueConstraint("institute_id", "name", name="uq_interview_templates_institute_name"),
        db.Index("ix_interview_templates_institute_id", "institute_id"),
    )

    def __repr__(self) -> str:
        return f"<InterviewTemplate {self.id} {self.name!r}>"


# Canonical ordering when a round's sequence isn't otherwise specified.
_DEFAULT_ROUND_ORDER = {
    InterviewRoundType.TECHNICAL: 1,
    InterviewRoundType.MANAGERIAL: 2,
    InterviewRoundType.HR: 3,
}


class InterviewTemplateRound(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "interview_template_rounds"

    template_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("interview_templates.id", ondelete="CASCADE"),
        nullable=False,
    )

    round_type = db.Column(db.String(16), nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)

    question_categories = db.Column(db.JSON, nullable=False, default=list)
    evaluation_criteria = db.Column(db.JSON, nullable=False, default=dict)
    instructions = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "template_id", "round_type", name="uq_template_rounds_template_round_type"
        ),
        db.CheckConstraint(
            f"round_type IN {InterviewRoundType.ALL}", name="ck_template_rounds_type_valid"
        ),
        db.CheckConstraint("duration_minutes > 0", name="ck_template_rounds_duration_positive"),
    )

    def __repr__(self) -> str:
        return f"<InterviewTemplateRound {self.round_type} template={self.template_id}>"
