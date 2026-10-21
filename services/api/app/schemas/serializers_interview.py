"""
Interview-specific serializers. Two shapes deliberately kept separate:
  - serialize_interview_admin(): full detail for institute admins
    (rounds, questions, answers, access token status — but never the
    raw access token itself, only whether it's expired).
  - serialize_interview_state(): what a student's own session sees —
    no other students' data reachable through this at all, since the
    session is scoped to exactly one interview.
"""
from app.models import Interview, InterviewQuestion, Evaluation


def serialize_evaluation(evaluation: Evaluation) -> dict:
    return {
        "dimension": evaluation.dimension,
        "score": evaluation.score,
        "criteria_scores": evaluation.criteria_scores,
        "evidence": evaluation.evidence,
        "strengths": evaluation.strengths,
        "weaknesses": evaluation.weaknesses,
        "improvement_suggestions": evaluation.improvement_suggestions,
        "evaluation_source": evaluation.evaluation_source,
    }


def serialize_question_public(question: InterviewQuestion | None) -> dict | None:
    if question is None:
        return None
    return {
        "id": str(question.id),
        "sequence_order": question.sequence_order,
        "question_text": question.question_text,
    }


def serialize_interview_state(interview: Interview, *, current_question=None) -> dict:
    current_round_obj = None
    if interview.current_round:
        current_round_obj = next(
            (r for r in interview.rounds if r.round_type == interview.current_round), None
        )

    return {
        "id": str(interview.id),
        "status": interview.status,
        "current_round": interview.current_round,
        "seconds_remaining": current_round_obj.seconds_remaining if current_round_obj else None,
        "resume_verified": interview.resume_verified,
        "device_checked": interview.device_checked,
        "technical_duration_minutes": interview.technical_duration_minutes,
        "managerial_duration_minutes": interview.managerial_duration_minutes,
        "hr_duration_minutes": interview.hr_duration_minutes,
        "current_question": serialize_question_public(current_question),
        "started_at": interview.started_at.isoformat() if interview.started_at else None,
        "completed_at": interview.completed_at.isoformat() if interview.completed_at else None,
    }


def serialize_interview_admin(interview: Interview, *, evaluations: list[Evaluation] | None = None) -> dict:
    import datetime as _dt

    rounds = []
    for r in sorted(interview.rounds, key=lambda r: r.sequence_order):
        questions = []
        for q in sorted(r.questions, key=lambda q: q.sequence_order):
            answer = q.answer
            questions.append(
                {
                    "id": str(q.id),
                    "sequence_order": q.sequence_order,
                    "question_text": q.question_text,
                    "question_source": q.question_source,
                    "topic": q.topic,
                    "asked_at": q.asked_at.isoformat() if q.asked_at else None,
                    "answer": {
                        "transcript_text": answer.transcript_text,
                        "answered_at": answer.answered_at.isoformat(),
                        "time_taken_seconds": answer.time_taken_seconds,
                    }
                    if answer
                    else None,
                }
            )
        rounds.append(
            {
                "round_type": r.round_type,
                "status": r.status,
                "duration_minutes": r.duration_minutes,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "questions": questions,
            }
        )

    now = _dt.datetime.now(_dt.timezone.utc)
    return {
        "id": str(interview.id),
        "campaign_id": str(interview.campaign_id),
        "student_id": str(interview.student_id),
        "status": interview.status,
        "current_round": interview.current_round,
        "resume_verified": interview.resume_verified,
        "device_checked": interview.device_checked,
        "access_token_expired": interview.access_token_expires_at < now,
        "started_at": interview.started_at.isoformat() if interview.started_at else None,
        "completed_at": interview.completed_at.isoformat() if interview.completed_at else None,
        "cancelled_at": interview.cancelled_at.isoformat() if interview.cancelled_at else None,
        "rounds": rounds,
        "evaluations": [serialize_evaluation(e) for e in evaluations] if evaluations else [],
        "created_at": interview.created_at.isoformat() if interview.created_at else None,
    }


def serialize_interview_summary(interview: Interview) -> dict:
    """Lighter shape for list views (campaign -> interviews list)."""
    return {
        "id": str(interview.id),
        "student_id": str(interview.student_id),
        "status": interview.status,
        "current_round": interview.current_round,
        "started_at": interview.started_at.isoformat() if interview.started_at else None,
        "completed_at": interview.completed_at.isoformat() if interview.completed_at else None,
    }
