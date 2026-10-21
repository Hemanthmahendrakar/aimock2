"""
Report — a student's mock interview report, versioned like Resume/
ResumeVersion (Phase 6): Report is a stable per-interview pointer,
ReportVersion holds one generation's actual content. Regenerating a
report (e.g. after switching AI_PROVIDER, or an admin-triggered
re-run) creates a new version rather than overwriting history — the
spec explicitly requires reports to be versioned.

Numeric scores are computed deterministically from Phase 10's
Evaluation rows (no AI needed for arithmetic). The narrative sections
(strengths, weaknesses, skill gaps, highlights, recommendations,
improvement plan) come from AIGateway.generate_report(), which
synthesizes across all four evaluations — that's the actual "report
generation" work an AI Gateway does here, not just paraphrasing.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Report(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "reports"

    interview_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    # Stored directly (not derived via interview->campaign->institute)
    # for the same reason Resume does this — every tenant-scoped query
    # filters on institute_id without an extra join.
    institute_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False
    )
    current_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("report_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    versions = db.relationship(
        "ReportVersion",
        foreign_keys="ReportVersion.report_id",
        backref="report",
        cascade="all, delete-orphan",
        order_by="ReportVersion.version_number",
    )
    current_version = db.relationship("ReportVersion", foreign_keys=[current_version_id])

    __table_args__ = (db.Index("ix_reports_institute_id", "institute_id"),)


class ReportVersion(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "report_versions"

    report_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    version_number = db.Column(db.Integer, nullable=False)

    # Headline scores (0-100). overall_score = round(mean of the four
    # dimension scores) — the spec's own report example doesn't total
    # to an unweighted mean of its four shown scores, but gives no
    # explicit formula either ("Example:" — illustrative, not a spec'd
    # calculation), so this is a stated, documented assumption.
    overall_score = db.Column(db.Integer, nullable=False)
    technical_score = db.Column(db.Integer, nullable=False)
    communication_score = db.Column(db.Integer, nullable=False)
    managerial_score = db.Column(db.Integer, nullable=False)
    hr_score = db.Column(db.Integer, nullable=False)
    # Pulled from the technical evaluation's own "problem_solving"
    # rubric criterion (see evaluation_rubrics.TECHNICAL_CRITERIA) —
    # the spec lists it as a headline score but it's not an
    # independent evaluation dimension of its own.
    problem_solving_score = db.Column(db.Integer, nullable=False)

    strengths = db.Column(db.JSON, nullable=False, default=list)
    weaknesses = db.Column(db.JSON, nullable=False, default=list)
    technical_skill_gaps = db.Column(db.JSON, nullable=False, default=list)
    communication_improvements = db.Column(db.JSON, nullable=False, default=list)
    interview_highlights = db.Column(db.JSON, nullable=False, default=list)
    recommended_preparation = db.Column(db.JSON, nullable=False, default=list)
    improvement_plan = db.Column(db.JSON, nullable=False, default=list)

    # Versioning metadata, per the spec's explicit requirement to track
    # model/prompt/evaluation/report version + generation timestamp.
    model_version = db.Column(db.String(64), nullable=True)  # e.g. AI_MODEL config value; null for heuristic
    prompt_version = db.Column(db.String(32), nullable=False, default="report_prompt_v1")
    # Summarizes the evaluation_source of the four Evaluation rows this
    # report was built from — "heuristic_v1"/"ai_v1" if all four agree,
    # "mixed_v1" if the AI Gateway fell back on some but not others.
    evaluation_version = db.Column(db.String(32), nullable=False)
    report_source = db.Column(db.String(64), nullable=False, default="heuristic_v1")

    generated_at = db.Column(db.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("report_id", "version_number", name="uq_report_versions_report_version"),
        db.CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="ck_report_versions_overall_range"),
        db.Index("ix_report_versions_report_id", "report_id"),
    )
