"""
Tests for Phase 10 (Evaluation Engine): the heuristic evaluators as
pure unit tests, and an end-to-end test proving an interview that
reaches COMPLETED actually gets evaluated automatically — this is the
integration point that was missing until this phase's audit added it
(see interview_service.py's _enqueue_evaluation).
"""
from datetime import datetime, timezone

from app.ai.gateway import AIGateway
from app.ai.types import AnsweredQuestion, RoundEvaluationContext, CommunicationEvaluationContext
from app.extensions import db
from app.models import User, UserStatus, Interview, Evaluation, EvaluationDimension
from app.services.heuristic_evaluator import (
    evaluate_communication_heuristically,
    evaluate_round_heuristically,
)
from app.services.evaluation_rubrics import criteria_for_dimension


def _register_and_activate(client, *, institute_name, institute_email, admin_email, password):
    payload = {
        "institute_name": institute_name,
        "institute_email": institute_email,
        "admin_full_name": "Admin",
        "admin_email": admin_email,
        "password": password,
    }
    client.post("/api/v1/institute/auth/register", json=payload)
    user = db.session.query(User).filter(User.email == admin_email).first()
    user.status = UserStatus.ACTIVE
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return user


def _login(client, email, password):
    return client.post(
        "/api/v1/institute/auth/login", json={"email": email, "password": password}
    )


def _setup_institute(client, suffix: str):
    _register_and_activate(
        client,
        institute_name=f"Institute {suffix}",
        institute_email=f"admissions@{suffix}.example",
        admin_email=f"admin@{suffix}.example",
        password="SuperSecret123",
    )
    _login(client, f"admin@{suffix}.example", "SuperSecret123")


class TestHeuristicCommunicationEvaluator:
    def test_empty_answers_returns_zero_score(self, app):
        with app.app_context():
            result = evaluate_communication_heuristically(CommunicationEvaluationContext(answers=[]))
            assert result.score == 0
            assert result.dimension == EvaluationDimension.COMMUNICATION

    def test_filler_heavy_answer_scores_lower_than_clean_answer(self, app):
        with app.app_context():
            clean = evaluate_communication_heuristically(
                CommunicationEvaluationContext(
                    answers=[
                        AnsweredQuestion(
                            question_text="Q",
                            answer_text=(
                                "I designed the system with a clear separation of "
                                "concerns between the API layer and the data layer."
                            ),
                            topic=None,
                            time_taken_seconds=30,
                        )
                    ]
                )
            )
            filler_heavy = evaluate_communication_heuristically(
                CommunicationEvaluationContext(
                    answers=[
                        AnsweredQuestion(
                            question_text="Q",
                            answer_text=(
                                "Um, so, like, I mean, basically I kind of, um, "
                                "sort of did the thing, you know, actually."
                            ),
                            topic=None,
                            time_taken_seconds=30,
                        )
                    ]
                )
            )
            assert filler_heavy.criteria_scores["filler_words"] < clean.criteria_scores["filler_words"]
            assert filler_heavy.score < clean.score

    def test_criteria_scores_cover_all_rubric_dimensions(self, app):
        with app.app_context():
            result = evaluate_communication_heuristically(
                CommunicationEvaluationContext(
                    answers=[
                        AnsweredQuestion(
                            question_text="Q", answer_text="A reasonably normal answer here.",
                            topic=None, time_taken_seconds=20,
                        )
                    ]
                )
            )
            assert set(result.criteria_scores.keys()) == set(
                criteria_for_dimension(EvaluationDimension.COMMUNICATION)
            )
            for score in result.criteria_scores.values():
                assert 0 <= score <= 100


class TestHeuristicRoundEvaluator:
    def test_empty_answers_returns_zero_score(self, app):
        with app.app_context():
            result = evaluate_round_heuristically(
                RoundEvaluationContext(
                    round_type="technical", difficulty="medium", target_role="Dev",
                    criteria_names=criteria_for_dimension("technical"), answers=[],
                    instructions=None,
                )
            )
            assert result.score == 0

    def test_score_never_claims_full_confidence(self, app):
        """
        The heuristic round evaluator explicitly should never produce
        a top score, since it can't judge content correctness — this
        is a deliberate honesty constraint, not an incidental one.
        """
        with app.app_context():
            long_answers = [
                AnsweredQuestion(
                    question_text="Q",
                    answer_text=" ".join(["word"] * 200),  # very long, still meaningless
                    topic="dsa",
                    time_taken_seconds=60,
                )
            ]
            result = evaluate_round_heuristically(
                RoundEvaluationContext(
                    round_type="technical", difficulty="medium", target_role="Dev",
                    criteria_names=criteria_for_dimension("technical"), answers=long_answers,
                    instructions=None,
                )
            )
            assert result.score <= 70

    def test_all_criteria_get_the_same_completeness_score(self, app):
        with app.app_context():
            answers = [
                AnsweredQuestion(
                    question_text="Q", answer_text="A short answer.", topic="ownership",
                    time_taken_seconds=15,
                )
            ]
            result = evaluate_round_heuristically(
                RoundEvaluationContext(
                    round_type="managerial", difficulty="medium", target_role="Dev",
                    criteria_names=criteria_for_dimension("managerial"), answers=answers,
                    instructions=None,
                )
            )
            assert len(set(result.criteria_scores.values())) == 1


class TestGatewayEvaluationFallback:
    def test_evaluate_answer_falls_back_to_heuristic_on_missing_key(self, app):
        app.config["AI_PROVIDER"] = "anthropic"
        app.config["AI_API_KEY"] = ""
        try:
            with app.app_context():
                gateway = AIGateway()
                result = gateway.evaluate_answer(
                    RoundEvaluationContext(
                        round_type="technical", difficulty="medium", target_role="Dev",
                        criteria_names=criteria_for_dimension("technical"), answers=[],
                        instructions=None,
                    )
                )
                assert result.source == "heuristic_v1"
        finally:
            app.config["AI_PROVIDER"] = "none"
            app.config["AI_API_KEY"] = ""


class TestEndToEndEvaluationTrigger:
    def _complete_full_interview(self, client, suffix: str) -> str:
        _setup_institute(client, suffix)
        student_resp = client.post(
            "/api/v1/institute/students",
            json={"name": "Student", "email": f"{suffix}s1@students.example"},
        )
        student_id = student_resp.get_json()["data"]["id"]
        campaign_resp = client.post(
            "/api/v1/institute/campaigns", json={"name": f"{suffix} Drive", "role": "Dev"}
        )
        campaign_id = campaign_resp.get_json()["data"]["id"]
        client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [student_id]},
        )
        client.post(f"/api/v1/institute/campaigns/{campaign_id}/activate")

        import uuid as uuid_mod
        from app.utils.security import generate_raw_token, hash_token

        interview = (
            db.session.query(Interview)
            .filter(
                Interview.campaign_id == uuid_mod.UUID(campaign_id),
                Interview.student_id == uuid_mod.UUID(student_id),
            )
            .first()
        )
        raw_token = generate_raw_token()
        interview.access_token_hash = hash_token(raw_token)
        db.session.commit()
        interview_id = str(interview.id)

        client.post(f"/api/v1/interview/{interview_id}/access", json={"token": raw_token})
        client.post("/api/v1/interview/resume-check")
        client.post("/api/v1/interview/device-check")
        client.post("/api/v1/interview/start")

        thorough_answer = (
            "I approached this methodically, considered the tradeoffs, and "
            "implemented a solution that balanced performance with maintainability."
        )
        for _ in range(30):  # generous safety cap
            state = client.get("/api/v1/interview/me").get_json()["data"]
            if state["status"] == "completed":
                break
            question = state["current_question"]
            if question is None:
                break
            client.post(
                "/api/v1/interview/answer",
                json={"question_id": question["id"], "transcript_text": thorough_answer},
            )
        else:
            assert False, "Interview did not complete"

        return interview_id

    def test_completing_interview_creates_all_four_evaluations(self, client):
        interview_id = self._complete_full_interview(client, "e2e1")

        import uuid as uuid_mod

        evaluations = (
            db.session.query(Evaluation)
            .filter(Evaluation.interview_id == uuid_mod.UUID(interview_id))
            .all()
        )
        dimensions = {e.dimension for e in evaluations}
        assert dimensions == set(EvaluationDimension.ALL)
        for e in evaluations:
            assert 0 <= e.score <= 100
            assert e.evaluation_source == "heuristic_v1"

    def test_interview_status_reaches_report_generating(self, client):
        interview_id = self._complete_full_interview(client, "e2e2")

        import uuid as uuid_mod

        interview = db.session.get(Interview, uuid_mod.UUID(interview_id))
        assert interview.status == "report_generating"
        assert interview.evaluated_at is not None
        assert interview.evaluation_error is None

    def test_admin_can_view_evaluations_via_interview_detail(self, client):
        interview_id = self._complete_full_interview(client, "e2e3")

        resp = client.get(f"/api/v1/institute/interviews/{interview_id}")
        data = resp.get_json()["data"]
        assert len(data["evaluations"]) == 4
        eval_dimensions = {e["dimension"] for e in data["evaluations"]}
        assert eval_dimensions == set(EvaluationDimension.ALL)
        for e in data["evaluations"]:
            assert "score" in e
            assert "evidence" in e
            assert "strengths" in e
            assert "weaknesses" in e
            assert "improvement_suggestions" in e

    def test_institute_b_cannot_view_institute_a_evaluations(self, client):
        interview_id = self._complete_full_interview(client, "e2e4")

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "e2e5")

        resp = client.get(f"/api/v1/institute/interviews/{interview_id}")
        assert resp.status_code == 404
