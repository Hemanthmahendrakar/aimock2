"""
Interview engine business logic, split into two concerns:
  - Admin side: creating interviews when a campaign activates, listing/
    viewing/cancelling them. institute_id here MUST be
    g.current_institute_id, same trust boundary as every other service.
  - Student session side: everything reachable only via a valid
    interview access token / session JWT (see require_interview_session
    in app/utils/authorization.py). These methods trust the `interview`
    object passed in, since obtaining it already proved the caller held
    a valid token for that specific interview.

Round/time progression is checked lazily (`_maybe_advance`) at the top
of every student-facing read/write — there's no scheduled sweep job.
Since every route call recomputes state against wall-clock time via
InterviewRound.seconds_remaining, a round can never appear open past
its actual duration even if nobody happens to poll during the exact
second it expires.

Question generation (Phase 8) goes entirely through AIGateway — this
file never imports a concrete provider. A round starts with an initial
batch of QUESTIONS_PER_ROUND_TARGET questions; after each answer,
AIGateway.generate_followup() gets a chance to insert one more before
_maybe_advance evaluates whether the round is done, capped by
MAX_QUESTIONS_PER_ROUND so a misbehaving provider can't loop forever.
_maybe_advance returns True only on the call that transitions the
interview to COMPLETED (end of the HR round); callers use that signal
to enqueue evaluation (app/tasks/evaluation_tasks.py) AFTER their own
commit, since the Celery task may run in a separate worker process
and needs COMPLETED already persisted, not just flushed in-session.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import (
    Interview,
    InterviewStatus,
    InterviewRound,
    RoundStatus,
    InterviewQuestion,
    InterviewAnswer,
    Campaign,
    CampaignStudent,
)
from app.models.interview_template import InterviewRoundType
from app.ai.gateway import AIGateway
from app.ai.types import QuestionContext, FollowupContext
from app.services.round_competencies import topics_for_round
from app.repositories.interview_repository import InterviewRepository
from app.repositories.student_repository import StudentRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.audit_service import AuditService
from app.services.mail_service import MailService
from app.utils.security import generate_raw_token, hash_token

_ROUND_SEQUENCE = [
    InterviewRoundType.TECHNICAL,
    InterviewRoundType.MANAGERIAL,
    InterviewRoundType.HR,
]


class InterviewServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InterviewNotFound(InterviewServiceError):
    def __init__(self):
        super().__init__("interview_not_found", "Interview not found.", 404)


class InvalidAccessToken(InterviewServiceError):
    def __init__(self):
        super().__init__(
            "invalid_access_token", "This interview link is invalid or has expired.", 401
        )


class InterviewNotReady(InterviewServiceError):
    def __init__(self, message: str):
        super().__init__("interview_not_ready", message, 409)


class InterviewNotActive(InterviewServiceError):
    def __init__(self):
        super().__init__(
            "interview_not_active", "This interview is not currently in progress.", 409
        )


class QuestionMismatch(InterviewServiceError):
    def __init__(self):
        super().__init__(
            "question_mismatch",
            "This is not the current question for this interview.",
            409,
        )


class AlreadyAnswered(InterviewServiceError):
    def __init__(self):
        super().__init__("already_answered", "This question has already been answered.", 409)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InterviewService:
    def __init__(self):
        self.interviews = InterviewRepository()
        self.students = StudentRepository()
        self.campaigns = CampaignRepository()
        self.resumes = ResumeRepository()
        self.audit = AuditService()
        self.mail = MailService()

    # ==================================================================
    # Admin side
    # ==================================================================
    def create_interviews_for_campaign(
        self, campaign: Campaign, *, institute_id: uuid.UUID
    ) -> dict:
        """
        Called when a campaign activates. Creates one Interview per
        currently-assigned roster student that doesn't already have
        one — safe to call more than once (e.g. re-activating), since
        it only fills in gaps.
        """
        from flask import current_app

        roster_student_ids = [
            row[0]
            for row in db.session.query(CampaignStudent.student_id)
            .filter(CampaignStudent.campaign_id == campaign.id)
            .all()
        ]

        created = 0
        skipped_existing = 0
        for student_id in roster_student_ids:
            existing = self.interviews.get_by_campaign_and_student(campaign.id, student_id)
            if existing is not None:
                skipped_existing += 1
                continue

            raw_token = generate_raw_token()
            interview = Interview(
                institute_id=institute_id,
                campaign_id=campaign.id,
                student_id=student_id,
                status=InterviewStatus.CREATED,
                access_token_hash=hash_token(raw_token),
                access_token_expires_at=_utcnow()
                + timedelta(days=current_app.config["INTERVIEW_ACCESS_TOKEN_TTL_DAYS"]),
                technical_duration_minutes=campaign.technical_duration_minutes,
                managerial_duration_minutes=campaign.managerial_duration_minutes,
                hr_duration_minutes=campaign.hr_duration_minutes,
            )
            self.interviews.create(interview)
            created += 1

            student = self.students.get_by_id(student_id, institute_id=institute_id)
            if student is not None:
                interview_link = (
                    f"{current_app.config['FRONTEND_ORIGIN']}/interview/{interview.id}"
                    f"?token={raw_token}"
                )
                self.mail.send_interview_invitation(
                    to_email=student.email,
                    student_name=student.name,
                    role=campaign.role,
                    interview_link=interview_link,
                )

        self.audit.log(
            event_type="campaign.interviews_created",
            institute_id=institute_id,
            metadata={
                "campaign_id": str(campaign.id),
                "created": created,
                "skipped_existing": skipped_existing,
            },
        )
        db.session.commit()
        return {"created": created, "already_existed": skipped_existing}

    def get_for_admin(self, interview_id: uuid.UUID, *, institute_id: uuid.UUID) -> Interview:
        interview = self.interviews.get_by_id(interview_id, institute_id=institute_id)
        if interview is None:
            raise InterviewNotFound()
        return interview

    def list_for_campaign(
        self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID, page: int, per_page: int
    ) -> tuple[list[Interview], int]:
        page = max(page, 1)
        per_page = min(max(per_page, 1), 100)
        return self.interviews.list_for_campaign(
            campaign_id, institute_id=institute_id, page=page, per_page=per_page
        )

    def cancel(self, interview_id: uuid.UUID, *, institute_id: uuid.UUID) -> Interview:
        interview = self.get_for_admin(interview_id, institute_id=institute_id)
        if interview.status in (InterviewStatus.COMPLETED, InterviewStatus.CANCELLED):
            raise InterviewNotReady(
                f"Cannot cancel an interview that is already {interview.status}."
            )
        interview.status = InterviewStatus.CANCELLED
        interview.cancelled_at = _utcnow()
        self.interviews.save(interview)
        self.audit.log(
            event_type="interview.cancelled", institute_id=institute_id,
            metadata={"interview_id": str(interview.id)},
        )
        db.session.commit()
        return interview

    # ==================================================================
    # Student session side
    # ==================================================================
    def exchange_access_token(self, interview_id: uuid.UUID, raw_token: str) -> Interview:
        interview = self.interviews.get_by_id_unscoped(interview_id)
        if interview is None or interview.access_token_hash != hash_token(raw_token):
            raise InvalidAccessToken()
        if interview.access_token_expires_at < _utcnow():
            raise InvalidAccessToken()
        if interview.status == InterviewStatus.CANCELLED:
            raise InterviewNotReady("This interview has been cancelled.")

        if interview.status == InterviewStatus.CREATED:
            interview.status = InterviewStatus.READY
            self.interviews.save(interview)
            self.audit.log(
                event_type="interview.accessed", institute_id=interview.institute_id,
                metadata={"interview_id": str(interview.id)},
            )
            db.session.commit()
        return interview

    def get_by_id_for_session(self, interview_id: uuid.UUID) -> Interview:
        interview = self.interviews.get_by_id_unscoped(interview_id)
        if interview is None:
            raise InterviewNotFound()
        return interview

    def mark_resume_verified(self, interview: Interview) -> Interview:
        interview.resume_verified = True
        self.interviews.save(interview)
        db.session.commit()
        return interview

    def mark_device_checked(self, interview: Interview) -> Interview:
        interview.device_checked = True
        self.interviews.save(interview)
        db.session.commit()
        return interview

    def start(self, interview: Interview) -> Interview:
        if interview.status != InterviewStatus.READY:
            raise InterviewNotReady(
                "The interview must be in the 'ready' state to start "
                f"(currently '{interview.status}')."
            )
        if not interview.resume_verified:
            raise InterviewNotReady("Please confirm your resume before starting.")
        if not interview.device_checked:
            raise InterviewNotReady(
                "Please complete the camera/microphone check before starting."
            )

        interview.status = InterviewStatus.IN_PROGRESS
        interview.current_round = InterviewRoundType.TECHNICAL
        interview.started_at = _utcnow()
        self.interviews.save(interview)

        self._create_round(interview, InterviewRoundType.TECHNICAL)

        self.audit.log(
            event_type="interview.started", institute_id=interview.institute_id,
            metadata={"interview_id": str(interview.id)},
        )
        db.session.commit()
        return interview

    def get_current_question(self, interview: Interview) -> InterviewQuestion | None:
        just_completed = self._maybe_advance(interview)
        db.session.commit()
        if just_completed:
            self._enqueue_evaluation(interview)
        if interview.status != InterviewStatus.IN_PROGRESS or interview.current_round is None:
            return None
        round_ = self.interviews.get_round(interview.id, interview.current_round)
        if round_ is None:
            return None
        return self._first_unanswered(round_)

    def submit_answer(
        self, interview: Interview, *, question_id: uuid.UUID, transcript_text: str
    ) -> Interview:
        self._maybe_advance(interview)
        if interview.status != InterviewStatus.IN_PROGRESS or interview.current_round is None:
            raise InterviewNotActive()

        round_ = self.interviews.get_round(interview.id, interview.current_round)
        current_question = self._first_unanswered(round_) if round_ else None
        if current_question is None or current_question.id != question_id:
            raise QuestionMismatch()
        if self.interviews.get_answer_for_question(question_id) is not None:
            raise AlreadyAnswered()

        now = _utcnow()
        reference_time = current_question.asked_at or round_.started_at or now
        time_taken = max(0, int((now - reference_time).total_seconds()))

        answer = InterviewAnswer(
            interview_question_id=question_id,
            transcript_text=transcript_text,
            answered_at=now,
            time_taken_seconds=time_taken,
        )
        self.interviews.create_answer(answer)

        self.audit.log(
            event_type="interview.answer_submitted", institute_id=interview.institute_id,
            metadata={"interview_id": str(interview.id), "question_id": str(question_id)},
        )

        # Give the AI Gateway a chance to insert a follow-up before
        # evaluating round completion — a freshly-inserted unanswered
        # question means _maybe_advance won't consider the round done
        # yet, so this must run first.
        self._maybe_generate_followup(interview, round_, current_question, transcript_text)

        just_completed = self._maybe_advance(interview)
        db.session.commit()
        if just_completed:
            self._enqueue_evaluation(interview)
        return interview

    # ------------------------------------------------------------------
    # Internal round/question machinery
    # ------------------------------------------------------------------
    def _create_round(self, interview: Interview, round_type: str) -> InterviewRound:
        from flask import current_app

        order = {rt: i + 1 for i, rt in enumerate(_ROUND_SEQUENCE)}
        round_ = InterviewRound(
            interview_id=interview.id,
            round_type=round_type,
            sequence_order=order[round_type],
            duration_minutes=interview.duration_for(round_type),
            status=RoundStatus.IN_PROGRESS,
            started_at=_utcnow(),
        )
        self.interviews.create_round(round_)

        campaign = self.campaigns.get_by_id(
            interview.campaign_id, institute_id=interview.institute_id
        )
        candidate_profile = self._candidate_profile_dict(interview)
        instructions = self._instructions_for_round(campaign, round_type)
        if campaign and getattr(campaign, "job_description", None):
            job_context = "Target job description (use as context; do not assume unstated requirements):\n" + campaign.job_description[:8000]
            instructions = f"{instructions}\n\n{job_context}" if instructions else job_context
        # Campaign-specific config wins when present (technical:
        # question_categories; managerial/HR: evaluation_criteria keys
        # copied from a template — see Phase 5); otherwise falls back
        # to the spec's default subject/competency list for this round.
        categories = topics_for_round(round_type, campaign)
        difficulty = campaign.difficulty if campaign else "medium"
        target_role = campaign.role if campaign else "the target role"
        if campaign and getattr(campaign, "company_id", None):
            from app.models import Company
            company = Company.query.filter(Company.id == campaign.company_id).first()
            if company:
                target_role = f"{target_role} at {company.name}"
        experience_level = campaign.experience_level if campaign else None

        gateway = AIGateway()
        now = _utcnow()
        previous_questions: list[str] = []
        target_count = current_app.config["QUESTIONS_PER_ROUND_TARGET"]

        # A campaign may use institute-curated questions, AI-generated questions,
        # or a mixture. Custom questions are always tenant-scoped and company-aware.
        custom_questions = []
        source_mode = getattr(campaign, "question_source", "ai") if campaign else "ai"
        if source_mode in ("custom", "mixed") and campaign is not None:
            from app.models import QuestionBankQuestion
            from sqlalchemy import or_
            custom_query = QuestionBankQuestion.query.filter_by(
                institute_id=interview.institute_id, round_type=round_type,
                is_active=True, deleted_at=None,
            )
            if getattr(campaign, "company_id", None):
                custom_query = custom_query.filter(or_(QuestionBankQuestion.company_id == campaign.company_id, QuestionBankQuestion.company_id.is_(None)))
            else:
                custom_query = custom_query.filter(QuestionBankQuestion.company_id.is_(None))
            if campaign.role:
                custom_query = custom_query.filter(or_(QuestionBankQuestion.role.is_(None), QuestionBankQuestion.role.ilike(campaign.role)))
            custom_questions = custom_query.order_by(QuestionBankQuestion.created_at.asc()).limit(target_count).all()

        for i in range(1, target_count + 1):
            use_custom = bool(custom_questions) and (source_mode == "custom" or (source_mode == "mixed" and i % 2 == 1))
            if use_custom:
                custom = custom_questions.pop(0)
                question_text = custom.question
                question_source = "institute_question_bank"
                topic = custom.category
            else:
                context = QuestionContext(
                round_type=round_type,
                difficulty=difficulty,
                target_role=target_role,
                experience_level=experience_level,
                question_categories=categories,
                instructions=instructions,
                candidate_profile=candidate_profile,
                previous_questions=previous_questions,
                previous_answers=[],  # nothing answered yet — round just started
                seconds_remaining=round_.seconds_remaining,
            )
                result = gateway.generate_question(context)
                question_text = result.question_text
                question_source = result.source
                topic = result.topic
            self.interviews.create_question(
                InterviewQuestion(
                    interview_round_id=round_.id,
                    sequence_order=i,
                    question_text=question_text,
                    question_source=question_source,
                    topic=topic,
                    asked_at=now if i == 1 else None,
                )
            )
            previous_questions.append(question_text)

        return round_

    def _maybe_generate_followup(
        self,
        interview: Interview,
        round_: InterviewRound,
        answered_question: InterviewQuestion,
        transcript_text: str,
    ) -> None:
        from flask import current_app

        if round_.seconds_remaining <= 0:
            return  # round's about to end regardless — don't add more work

        total_questions = self.interviews.count_questions(round_.id)
        max_per_round = current_app.config["MAX_QUESTIONS_PER_ROUND"]
        if total_questions >= max_per_round:
            return

        target_count = current_app.config["QUESTIONS_PER_ROUND_TARGET"]
        followups_so_far = max(0, total_questions - target_count)

        campaign = self.campaigns.get_by_id(
            interview.campaign_id, institute_id=interview.institute_id
        )
        instructions = self._instructions_for_round(campaign, round_.round_type)
        difficulty = campaign.difficulty if campaign else "medium"

        context = FollowupContext(
            round_type=round_.round_type,
            difficulty=difficulty,
            original_question=answered_question.question_text,
            answer_text=transcript_text,
            instructions=instructions,
            followups_asked_so_far=followups_so_far,
        )
        result = AIGateway().generate_followup(context)
        if result is None:
            return

        next_order = max((q.sequence_order for q in round_.questions), default=0) + 1
        self.interviews.create_question(
            InterviewQuestion(
                interview_round_id=round_.id,
                sequence_order=next_order,
                question_text=result.question_text,
                question_source=result.source,
                topic=result.topic or answered_question.topic,
                asked_at=_utcnow(),
            )
        )

    def _candidate_profile_dict(self, interview: Interview) -> dict:
        profile = self.resumes.get_current_profile_for_student(
            interview.student_id, institute_id=interview.institute_id
        )
        if profile is None:
            return {}
        return {
            "skills": profile.skills,
            "programming_languages": profile.programming_languages,
            "technologies": profile.technologies,
            "projects": profile.projects,
            "internships": profile.internships,
            "experience": profile.experience,
            "education": profile.education,
            "certifications": profile.certifications,
            "achievements": profile.achievements,
        }

    def _instructions_for_round(
        self, campaign: Campaign | None, round_type: str
    ) -> str | None:
        if campaign is None:
            return None
        return {
            InterviewRoundType.TECHNICAL: campaign.technical_instructions,
            InterviewRoundType.MANAGERIAL: campaign.managerial_instructions,
            InterviewRoundType.HR: campaign.hr_instructions,
        }.get(round_type)

    def _first_unanswered(self, round_: InterviewRound) -> InterviewQuestion | None:
        for q in sorted(round_.questions, key=lambda q: q.sequence_order):
            if self.interviews.get_answer_for_question(q.id) is None:
                return q
        return None

    def _maybe_advance(self, interview: Interview) -> bool:
        """
        Returns True only when THIS call is the one that transitions
        the interview to COMPLETED — callers use that to enqueue
        evaluation, but only after they've committed (the Celery task
        may run in a separate process/worker and needs the COMPLETED
        status already persisted, not just flushed in this session).
        """
        if interview.status != InterviewStatus.IN_PROGRESS or interview.current_round is None:
            return False

        round_ = self.interviews.get_round(interview.id, interview.current_round)
        if round_ is None or round_.status != RoundStatus.IN_PROGRESS:
            return False

        total_questions = self.interviews.count_questions(round_.id)
        answered_count = sum(
            1 for q in round_.questions
            if self.interviews.get_answer_for_question(q.id) is not None
        )
        time_up = round_.seconds_remaining <= 0
        all_answered = total_questions > 0 and answered_count >= total_questions

        if time_up or all_answered:
            round_.status = RoundStatus.COMPLETED
            round_.completed_at = _utcnow()
            self.interviews.save_round(round_)

            current_index = _ROUND_SEQUENCE.index(interview.current_round)
            if current_index + 1 < len(_ROUND_SEQUENCE):
                next_round_type = _ROUND_SEQUENCE[current_index + 1]
                interview.current_round = next_round_type
                self.interviews.save(interview)
                self._create_round(interview, next_round_type)
                return False
            else:
                interview.status = InterviewStatus.COMPLETED
                interview.current_round = None
                interview.completed_at = _utcnow()
                self.interviews.save(interview)
                self.audit.log(
                    event_type="interview.completed", institute_id=interview.institute_id,
                    metadata={"interview_id": str(interview.id)},
                )
                return True

        # Same round, not yet complete: make sure the next unanswered
        # question is marked as "asked" (for accurate time-taken on
        # its eventual answer), if it isn't already.
        next_q = self._first_unanswered(round_)
        if next_q is not None and next_q.asked_at is None:
            next_q.asked_at = _utcnow()
            self.interviews.save_question(next_q)
        return False

    def _enqueue_evaluation(self, interview: Interview) -> None:
        from app.tasks.evaluation_tasks import evaluate_interview_task

        evaluate_interview_task.delay(str(interview.id))
