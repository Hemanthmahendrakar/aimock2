import uuid
from typing import Optional

from app.extensions import db
from app.models import Interview, InterviewRound, InterviewQuestion, InterviewAnswer


class InterviewRepository:
    # --- Interview (institute-scoped, for admin use) --------------------
    def get_by_id(
        self, interview_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> Optional[Interview]:
        return (
            db.session.query(Interview)
            .filter(Interview.id == interview_id, Interview.institute_id == institute_id)
            .first()
        )

    def get_by_id_unscoped(self, interview_id: uuid.UUID) -> Optional[Interview]:
        """Used only by the interview-session lookup, which authenticates
        via access token / session JWT rather than an institute admin
        session — there is no institute_id to scope by at that point."""
        return db.session.get(Interview, interview_id)

    def get_by_access_token_hash(self, token_hash: str) -> Optional[Interview]:
        return (
            db.session.query(Interview)
            .filter(Interview.access_token_hash == token_hash)
            .first()
        )

    def get_by_campaign_and_student(
        self, campaign_id: uuid.UUID, student_id: uuid.UUID
    ) -> Optional[Interview]:
        return (
            db.session.query(Interview)
            .filter(Interview.campaign_id == campaign_id, Interview.student_id == student_id)
            .first()
        )

    def list_for_campaign(
        self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID, page: int, per_page: int
    ) -> tuple[list[Interview], int]:
        query = db.session.query(Interview).filter(
            Interview.campaign_id == campaign_id, Interview.institute_id == institute_id
        )
        total = query.count()
        items = (
            query.order_by(Interview.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def create(self, interview: Interview) -> Interview:
        db.session.add(interview)
        db.session.flush()
        return interview

    def save(self, interview: Interview) -> Interview:
        db.session.add(interview)
        db.session.flush()
        return interview

    # --- Rounds -----------------------------------------------------
    def create_round(self, round_: InterviewRound) -> InterviewRound:
        db.session.add(round_)
        db.session.flush()
        return round_

    def save_round(self, round_: InterviewRound) -> InterviewRound:
        db.session.add(round_)
        db.session.flush()
        return round_

    def get_round(
        self, interview_id: uuid.UUID, round_type: str
    ) -> Optional[InterviewRound]:
        return (
            db.session.query(InterviewRound)
            .filter(
                InterviewRound.interview_id == interview_id,
                InterviewRound.round_type == round_type,
            )
            .first()
        )

    # --- Questions ----------------------------------------------------
    def create_question(self, question: InterviewQuestion) -> InterviewQuestion:
        db.session.add(question)
        db.session.flush()
        return question

    def save_question(self, question: InterviewQuestion) -> InterviewQuestion:
        db.session.add(question)
        db.session.flush()
        return question

    def get_question(
        self, round_id: uuid.UUID, sequence_order: int
    ) -> Optional[InterviewQuestion]:
        return (
            db.session.query(InterviewQuestion)
            .filter(
                InterviewQuestion.interview_round_id == round_id,
                InterviewQuestion.sequence_order == sequence_order,
            )
            .first()
        )

    def count_questions(self, round_id: uuid.UUID) -> int:
        return (
            db.session.query(InterviewQuestion)
            .filter(InterviewQuestion.interview_round_id == round_id)
            .count()
        )

    # --- Answers ------------------------------------------------------
    def create_answer(self, answer: InterviewAnswer) -> InterviewAnswer:
        db.session.add(answer)
        db.session.flush()
        return answer

    def get_answer_for_question(
        self, question_id: uuid.UUID
    ) -> Optional[InterviewAnswer]:
        return (
            db.session.query(InterviewAnswer)
            .filter(InterviewAnswer.interview_question_id == question_id)
            .first()
        )
