"""
Tests for the AI Gateway. Everything here runs with AI_PROVIDER="none"
(the test-config default) — these tests must never require network
access. The one exception is TestGatewayFallback, which deliberately
configures AI_PROVIDER="anthropic" with no API key to exercise the
gateway's fallback-on-failure path using a failure mode (missing key)
that happens before any HTTP call is attempted.
"""
from datetime import datetime, timezone

from app.ai.gateway import AIGateway
from app.ai.providers.heuristic_provider import HeuristicProvider
from app.ai.types import QuestionContext, FollowupContext
from app.extensions import db
from app.models import User, UserStatus, Interview, InterviewRound


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


def _create_student(client, email_suffix: str):
    resp = client.post(
        "/api/v1/institute/students",
        json={"name": "Student", "email": f"{email_suffix}@students.example"},
    )
    return resp.get_json()["data"]["id"]


def _create_and_start_interview(client, suffix: str) -> str:
    _setup_institute(client, suffix)
    student_id = _create_student(client, f"{suffix}s1")
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
    return interview_id


class TestHeuristicProviderUnit:
    def test_analyze_resume_delegates_to_candidate_profile_builder(self, app):
        with app.app_context():
            provider = HeuristicProvider()
            result = provider.analyze_resume(
                "SKILLS\nPython, SQL\n\nEDUCATION\nB.Tech Computer Science"
            )
            assert result.extraction_method == "heuristic_v1"
            assert isinstance(result.skills, list)

    def test_generate_question_avoids_repeating_previous_questions(self, app):
        with app.app_context():
            provider = HeuristicProvider()
            first = provider.generate_question(
                QuestionContext(
                    round_type="technical", difficulty="medium", target_role="Dev",
                    experience_level=None, question_categories=[], instructions=None,
                    candidate_profile={}, previous_questions=[], previous_answers=[],
                    seconds_remaining=900,
                )
            )
            second = provider.generate_question(
                QuestionContext(
                    round_type="technical", difficulty="medium", target_role="Dev",
                    experience_level=None, question_categories=[], instructions=None,
                    candidate_profile={}, previous_questions=[first.question_text],
                    previous_answers=[], seconds_remaining=900,
                )
            )
            assert second.question_text != first.question_text
            assert first.source == "heuristic_v1"

    def test_generate_followup_triggers_on_short_answer(self, app):
        with app.app_context():
            provider = HeuristicProvider()
            result = provider.generate_followup(
                FollowupContext(
                    round_type="technical", difficulty="medium",
                    original_question="Tell me about a project.",
                    answer_text="I built a website.",  # 4 words — short
                    instructions=None, followups_asked_so_far=0,
                )
            )
            assert result is not None
            assert result.source == "heuristic_v1"

    def test_generate_followup_skips_on_thorough_answer(self, app):
        with app.app_context():
            provider = HeuristicProvider()
            result = provider.generate_followup(
                FollowupContext(
                    round_type="technical", difficulty="medium",
                    original_question="Tell me about a project.",
                    answer_text=(
                        "I built a full-stack web application using React and Flask, "
                        "designed the database schema myself, and deployed it to AWS "
                        "with a CI/CD pipeline I set up using GitHub Actions."
                    ),
                    instructions=None, followups_asked_so_far=0,
                )
            )
            assert result is None

    def test_followup_probes_cycle_without_immediate_repeat(self, app):
        with app.app_context():
            provider = HeuristicProvider()
            first = provider.generate_followup(
                FollowupContext(
                    round_type="technical", difficulty="medium", original_question="Q",
                    answer_text="Short.", instructions=None, followups_asked_so_far=0,
                )
            )
            second = provider.generate_followup(
                FollowupContext(
                    round_type="technical", difficulty="medium", original_question="Q",
                    answer_text="Short.", instructions=None, followups_asked_so_far=1,
                )
            )
            assert first.question_text != second.question_text


class TestGatewayFallback:
    def test_gateway_falls_back_to_heuristic_when_provider_misconfigured(self, app):
        """
        AI_PROVIDER="anthropic" with no API key fails before any network
        call (AnthropicProvider._call_json raises immediately on a
        missing key) — this exercises the real fallback path without
        needing network access.
        """
        app.config["AI_PROVIDER"] = "anthropic"
        app.config["AI_API_KEY"] = ""
        try:
            with app.app_context():
                gateway = AIGateway()
                result = gateway.generate_question(
                    QuestionContext(
                        round_type="technical", difficulty="medium", target_role="Dev",
                        experience_level=None, question_categories=[], instructions=None,
                        candidate_profile={}, previous_questions=[], previous_answers=[],
                        seconds_remaining=900,
                    )
                )
                assert result.source == "heuristic_v1"
        finally:
            app.config["AI_PROVIDER"] = "none"
            app.config["AI_API_KEY"] = ""

    def test_gateway_uses_heuristic_directly_when_provider_is_none(self, app):
        with app.app_context():
            gateway = AIGateway()
            result = gateway.generate_question(
                QuestionContext(
                    round_type="hr", difficulty="medium", target_role="Dev",
                    experience_level=None, question_categories=[], instructions=None,
                    candidate_profile={}, previous_questions=[], previous_answers=[],
                    seconds_remaining=900,
                )
            )
            assert result.source == "heuristic_v1"


class TestAdaptiveFollowupIntegration:
    def test_thorough_answers_do_not_grow_round_beyond_target(self, client):
        interview_id = _create_and_start_interview(client, "af1")
        thorough_answer = (
            "I designed and implemented the entire feature end to end, including "
            "the database schema, the API layer, and the frontend integration, "
            "and I wrote tests covering the main edge cases."
        )

        for _ in range(3):
            state = client.get("/api/v1/interview/me").get_json()["data"]
            if state["current_round"] != "technical":
                break
            question = state["current_question"]
            client.post(
                "/api/v1/interview/answer",
                json={"question_id": question["id"], "transcript_text": thorough_answer},
            )

        import uuid as uuid_mod

        round_ = (
            db.session.query(InterviewRound)
            .filter(
                InterviewRound.interview_id == uuid_mod.UUID(interview_id),
                InterviewRound.round_type == "technical",
            )
            .first()
        )
        # 3 thorough answers to a 3-question target round: no follow-ups
        # should have been inserted, so the round has exactly 3 questions.
        assert len(round_.questions) == 3

    def test_short_answers_add_followups_up_to_the_cap(self, client):
        interview_id = _create_and_start_interview(client, "af2")
        short_answer = "Not sure."

        import uuid as uuid_mod

        # Answer repeatedly until the round advances or we hit a safety
        # cap far above MAX_QUESTIONS_PER_ROUND, to avoid an infinite loop
        # if something regresses.
        for _ in range(10):
            round_ = (
                db.session.query(InterviewRound)
                .filter(
                    InterviewRound.interview_id == uuid_mod.UUID(interview_id),
                    InterviewRound.round_type == "technical",
                )
                .first()
            )
            if round_.status == "completed":
                break
            state = client.get("/api/v1/interview/me").get_json()["data"]
            if state["current_round"] != "technical":
                break
            question = state["current_question"]
            if question is None:
                break
            client.post(
                "/api/v1/interview/answer",
                json={"question_id": question["id"], "transcript_text": short_answer},
            )

        final_round = (
            db.session.query(InterviewRound)
            .filter(
                InterviewRound.interview_id == uuid_mod.UUID(interview_id),
                InterviewRound.round_type == "technical",
            )
            .first()
        )
        # Short answers keep triggering follow-ups, so the round should
        # grow past the initial target — but never past the hard cap.
        assert len(final_round.questions) > 3
        assert len(final_round.questions) <= 6
