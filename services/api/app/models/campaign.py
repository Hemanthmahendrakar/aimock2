"""
Campaign — an institute-run mock-interview drive (e.g. "Software
Developer Mock Interview - 2027"), carrying the interview configuration
that will apply to every student assigned to it: round durations,
interviewer avatar/voice, difficulty, question categories, evaluation
criteria.

Unlike Student/User, institute_id is NOT nullable here — there is no
Individual Mode concept of a "campaign" in the roadmap, so there's no
future-reuse reason to leave it optional.

Round duration DEFAULTS live in app.config (TECHNICAL_ROUND_DEFAULT_MINUTES
etc), applied by CampaignService at creation time if the admin doesn't
supply a value. This model intentionally has no column-level default
for those fields, so there's exactly one place (config) that owns the
default number — not two.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


class CampaignStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

    ALL = (DRAFT, ACTIVE, COMPLETED, ARCHIVED)


class CampaignDifficulty:
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    ALL = (EASY, MEDIUM, HARD)


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "campaigns"

    institute_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Records which template (if any) this campaign's round config was
    # seeded from at creation time — for display/audit only. SET NULL
    # on template deletion: the campaign keeps its own copied values
    # regardless (see InterviewTemplate's docstring on copy-not-link).
    interview_template_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("interview_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    campus_id = db.Column(UUID(as_uuid=True), db.ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True)
    job_description = db.Column(db.Text, nullable=True)
    question_source = db.Column(db.String(16), nullable=False, default="ai")

    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255), nullable=False)
    experience_level = db.Column(db.String(64), nullable=True)
    department = db.Column(db.String(128), nullable=True)
    batch = db.Column(db.String(32), nullable=True)

    # Round durations, in minutes. CampaignService fills these from a
    # template and/or app.config defaults if the admin doesn't specify
    # them — no column-level default here, so there's a single place
    # (config, or the chosen template) that owns the default number.
    technical_duration_minutes = db.Column(db.Integer, nullable=False)
    managerial_duration_minutes = db.Column(db.Integer, nullable=False)
    hr_duration_minutes = db.Column(db.Integer, nullable=False)

    # Free-text guidance for each round, surfaced to the AI Gateway
    # starting Phase 8. Copied from a template's per-round
    # `instructions` field if one was applied, editable afterward.
    technical_instructions = db.Column(db.Text, nullable=True)
    managerial_instructions = db.Column(db.Text, nullable=True)
    hr_instructions = db.Column(db.Text, nullable=True)

    # Free-form provider identifiers. Validated against real avatar/
    # voice providers starting Phase 13 — an enum here now would mean
    # a migration later once those providers actually exist.
    interviewer_avatar = db.Column(db.String(128), nullable=True)
    interviewer_voice = db.Column(db.String(128), nullable=True)
    interview_style = db.Column(db.String(64), nullable=True)

    difficulty = db.Column(db.String(16), nullable=False, default=CampaignDifficulty.MEDIUM)

    # JSON on purpose — the exact shape of question categories and
    # evaluation criteria will grow through Phases 8-10 without a
    # migration each time.
    question_categories = db.Column(db.JSON, nullable=False, default=list)
    evaluation_criteria = db.Column(db.JSON, nullable=False, default=dict)

    status = db.Column(db.String(16), nullable=False, default=CampaignStatus.DRAFT)

    __table_args__ = (
        db.CheckConstraint(f"status IN {CampaignStatus.ALL}", name="ck_campaigns_status_valid"),
        db.CheckConstraint(
            f"difficulty IN {CampaignDifficulty.ALL}", name="ck_campaigns_difficulty_valid"
        ),
        db.CheckConstraint("question_source IN ('ai','custom','mixed')", name="ck_campaigns_question_source_valid"),
        db.CheckConstraint(
            "technical_duration_minutes > 0", name="ck_campaigns_tech_duration_positive"
        ),
        db.CheckConstraint(
            "managerial_duration_minutes > 0", name="ck_campaigns_mgr_duration_positive"
        ),
        db.CheckConstraint("hr_duration_minutes > 0", name="ck_campaigns_hr_duration_positive"),
        db.Index("ix_campaigns_institute_status", "institute_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.id} {self.name!r}>"

    @property
    def total_duration_minutes(self) -> int:
        return (
            self.technical_duration_minutes
            + self.managerial_duration_minutes
            + self.hr_duration_minutes
        )


class CampaignStudent(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    """Roster assignment: which students are part of a campaign."""

    __tablename__ = "campaign_students"

    campaign_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    student_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "campaign_id", "student_id", name="uq_campaign_students_campaign_student"
        ),
        db.Index("ix_campaign_students_campaign_id", "campaign_id"),
        db.Index("ix_campaign_students_student_id", "student_id"),
    )
