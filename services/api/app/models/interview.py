"""
Interview engine — live state for an actual conducted interview. This
is distinct from InterviewTemplate/InterviewTemplateRound (Phase 5),
which are authored presets: creating an Interview COPIES the relevant
config (round durations) from its Campaign at that moment, so editing
a campaign afterward never reshapes an interview already in progress.

Status is deliberately coarse-grained (CREATED/READY/IN_PROGRESS/
COMPLETED/...); which of the three rounds is active lives in
`current_round` instead. The spec's status list also names TECHNICAL/
MANAGERIAL/HR as states, but the spec separately requires the backend
to track "current round" and "interview state" as two distinct pieces
of information — treating those three as round detail under a single
IN_PROGRESS status satisfies both without conflating two concerns into
one enum. Stated assumption, flagged for review.

EVALUATING/REPORT_GENERATING/REPORT_READY exist in the enum (the spec
lists them as valid states). Phase 10 transitions COMPLETED ->
EVALUATING -> REPORT_GENERATING once all four dimension evaluations
are saved (see app/tasks/evaluation_tasks.py); REPORT_GENERATING ->
REPORT_READY is Phase 11's job.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.interview_template import InterviewRoundType


class InterviewStatus:
    CREATED = "created"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EVALUATING = "evaluating"
    REPORT_GENERATING = "report_generating"
    REPORT_READY = "report_ready"
    FAILED = "failed"
    CANCELLED = "cancelled"

    ALL = (
        CREATED, READY, IN_PROGRESS, COMPLETED, EVALUATING,
        REPORT_GENERATING, REPORT_READY, FAILED, CANCELLED,
    )


class RoundStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

    ALL = (PENDING, IN_PROGRESS, COMPLETED)


_ROUND_ORDER = {
    InterviewRoundType.TECHNICAL: 1,
    InterviewRoundType.MANAGERIAL: 2,
    InterviewRoundType.HR: 3,
}


class Interview(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "interviews"

    institute_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    student_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )

    status = db.Column(db.String(24), nullable=False, default=InterviewStatus.CREATED)
    current_round = db.Column(db.String(16), nullable=True)  # technical|managerial|hr|null

    # Hashed the same way as email-verification/password-reset tokens
    # (Phase 1) — the raw token is only ever in the invite link, never
    # persisted. Exchanged once for a session JWT; not burned after
    # first use, since a student may reload the lobby before starting.
    access_token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    access_token_expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    resume_verified = db.Column(db.Boolean, nullable=False, default=False)
    device_checked = db.Column(db.Boolean, nullable=False, default=False)

    # Copied from Campaign at creation time — see module docstring.
    technical_duration_minutes = db.Column(db.Integer, nullable=False)
    managerial_duration_minutes = db.Column(db.Integer, nullable=False)
    hr_duration_minutes = db.Column(db.Integer, nullable=False)

    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Set by evaluate_interview_task (Phase 10) once all four
    # dimension evaluations are saved. evaluation_error is set only if
    # the task fails outright (DB/unexpected error) — an individual
    # AI Gateway call failing on one dimension already falls back to
    # the heuristic provider rather than failing the whole task.
    evaluated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    evaluation_error = db.Column(db.Text, nullable=True)
    report_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    report_generation_error = db.Column(db.Text, nullable=True)

    rounds = db.relationship(
        "InterviewRound",
        backref="interview",
        cascade="all, delete-orphan",
        order_by="InterviewRound.sequence_order",
    )

    __table_args__ = (
        db.UniqueConstraint("campaign_id", "student_id", name="uq_interviews_campaign_student"),
        db.CheckConstraint(f"status IN {InterviewStatus.ALL}", name="ck_interviews_status_valid"),
        db.Index("ix_interviews_institute_id", "institute_id"),
        db.Index("ix_interviews_campaign_id", "campaign_id"),
        db.Index("ix_interviews_student_id", "student_id"),
    )

    def duration_for(self, round_type: str) -> int:
        return {
            InterviewRoundType.TECHNICAL: self.technical_duration_minutes,
            InterviewRoundType.MANAGERIAL: self.managerial_duration_minutes,
            InterviewRoundType.HR: self.hr_duration_minutes,
        }[round_type]

    def __repr__(self) -> str:
        return f"<Interview {self.id} status={self.status} round={self.current_round}>"


class InterviewRound(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "interview_rounds"

    interview_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False
    )
    round_type = db.Column(db.String(16), nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, default=RoundStatus.PENDING)

    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    questions = db.relationship(
        "InterviewQuestion",
        backref="round",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.sequence_order",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "interview_id", "round_type", name="uq_interview_rounds_interview_round_type"
        ),
        db.CheckConstraint(
            f"round_type IN {InterviewRoundType.ALL}", name="ck_interview_rounds_type_valid"
        ),
        db.CheckConstraint(
            f"status IN {RoundStatus.ALL}", name="ck_interview_rounds_status_valid"
        ),
        db.Index("ix_interview_rounds_interview_id", "interview_id"),
    )

    @property
    def seconds_remaining(self) -> int:
        if self.started_at is None:
            return self.duration_minutes * 60
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return max(0, int(self.duration_minutes * 60 - elapsed))

    def __repr__(self) -> str:
        return f"<InterviewRound {self.round_type} interview={self.interview_id}>"


class InterviewQuestion(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "interview_questions"

    interview_round_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_order = db.Column(db.Integer, nullable=False)
    question_text = db.Column(db.Text, nullable=False)

    # Set by whichever AI Gateway provider generated this question —
    # "heuristic_v1" (default/offline) or "ai_v1" (real provider). The
    # column default is a defensive fallback only; application code
    # always sets this explicitly from the provider's tag.
    question_source = db.Column(db.String(64), nullable=False, default="heuristic_v1")

    # Which competency/subject area (e.g. "dbms", "ownership") this
    # question targets — set by the heuristic provider, which picks
    # from a structured bank; left null for AI-generated questions that
    # don't commit to one of a fixed taxonomy. Phase 10's evaluation
    # engine uses this to grade against the right rubric dimension.
    topic = db.Column(db.String(64), nullable=True)

    asked_at = db.Column(db.DateTime(timezone=True), nullable=True)

    answer = db.relationship(
        "InterviewAnswer", backref="question", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "interview_round_id", "sequence_order",
            name="uq_interview_questions_round_sequence",
        ),
        db.Index("ix_interview_questions_round_id", "interview_round_id"),
    )

    def __repr__(self) -> str:
        return f"<InterviewQuestion {self.id} round={self.interview_round_id}>"


class InterviewAnswer(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    __tablename__ = "interview_answers"

    interview_question_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("interview_questions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # What the spec calls "transcript" is folded in here rather than a
    # separate table — there's no live speech-to-text pipeline until
    # Phase 13, so today this is simply the student's typed answer.
    transcript_text = db.Column(db.Text, nullable=False)
    answered_at = db.Column(db.DateTime(timezone=True), nullable=False)
    time_taken_seconds = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "interview_question_id", name="uq_interview_answers_question_id"
        ),
    )

    def __repr__(self) -> str:
        return f"<InterviewAnswer {self.id} question={self.interview_question_id}>"
