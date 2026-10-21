"""
Tests for Phase 9 (Technical + Managerial + HR round specialization):
round_competencies.topics_for_round precedence rules, the heuristic
bank's topic rotation and resume-grounded question type, and that a
question's topic is actually persisted end-to-end through a live
interview (not just computed and discarded).
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models import User, UserStatus, Campaign, Interview, InterviewRound
from app.services.round_competencies import (
    topics_for_round,
    DEFAULT_TECHNICAL_TOPICS,
    DEFAULT_MANAGERIAL_COMPETENCIES,
    DEFAULT_HR_COMPETENCIES,
)
from app.services.interview_question_bank import pick_question


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


class TestTopicsForRoundDefaults:
    def test_technical_falls_back_to_spec_default_topics(self, app):
        with app.app_context():
            assert topics_for_round("technical", None) == DEFAULT_TECHNICAL_TOPICS

    def test_managerial_falls_back_to_spec_default_competencies(self, app):
        with app.app_context():
            assert topics_for_round("managerial", None) == DEFAULT_MANAGERIAL_COMPETENCIES

    def test_hr_falls_back_to_spec_default_competencies(self, app):
        with app.app_context():
            assert topics_for_round("hr", None) == DEFAULT_HR_COMPETENCIES

    def test_unknown_round_type_returns_empty(self, app):
        with app.app_context():
            assert topics_for_round("nonsense", None) == []


class TestTopicsForRoundCampaignOverride:
    def test_technical_uses_campaign_question_categories_when_set(self, app):
        campaign = Campaign(question_categories=["dsa", "networking_only"], evaluation_criteria={})
        with app.app_context():
            assert topics_for_round("technical", campaign) == ["dsa", "networking_only"]

    def test_managerial_uses_campaign_evaluation_criteria_keys_when_set(self, app):
        campaign = Campaign(
            question_categories=[],
            evaluation_criteria={"managerial": {"ownership": 1.0, "leadership": 0.5}},
        )
        with app.app_context():
            result = topics_for_round("managerial", campaign)
            assert set(result) == {"ownership", "leadership"}

    def test_hr_falls_back_when_campaign_has_no_hr_criteria(self, app):
        campaign = Campaign(
            question_categories=[], evaluation_criteria={"managerial": {"ownership": 1.0}}
        )
        with app.app_context():
            assert topics_for_round("hr", campaign) == DEFAULT_HR_COMPETENCIES


class TestQuestionBankTopicRotation:
    def test_pick_question_rotates_across_topics(self, app):
        with app.app_context():
            topics = ["dsa", "algorithms", "oop"]
            seen_topics = []
            exclude: list[str] = []
            for i in range(3):
                text, topic = pick_question(
                    "technical", topics=topics, exclude=exclude, question_index=i
                )
                seen_topics.append(topic)
                exclude.append(text)
            # Rotation means three consecutive questions shouldn't all
            # land on the same topic.
            assert len(set(seen_topics)) > 1

    def test_pick_question_never_returns_an_excluded_question(self, app):
        with app.app_context():
            topics = ["dsa"]
            first_text, _ = pick_question("technical", topics=topics, exclude=[], question_index=0)
            second_text, _ = pick_question(
                "technical", topics=topics, exclude=[first_text], question_index=1
            )
            assert second_text != first_text

    def test_managerial_questions_are_scenario_phrased(self, app):
        """
        Spot-checks the spec's 'use scenario-based questions where
        appropriate' requirement for the managerial round — every bank
        question should read as a situational prompt (Imagine/Describe/
        Tell me about a time/How do you), not a bare abstract question.
        """
        with app.app_context():
            scenario_openers = ("imagine", "describe", "tell me about a time", "how do you", "walk me through", "pick a project")
            topics = list(DEFAULT_MANAGERIAL_COMPETENCIES)
            exclude: list[str] = []
            for i in range(len(topics)):
                text, _ = pick_question(
                    "managerial", topics=topics, exclude=exclude, question_index=i
                )
                exclude.append(text)
                assert text.lower().startswith(scenario_openers), f"Not scenario-phrased: {text}"

    def test_resume_grounded_question_uses_candidate_skill(self, app):
        with app.app_context():
            candidate_profile = {"skills": ["Kubernetes"]}
            found_resume_grounded = False
            exclude: list[str] = []
            for i in range(6):
                text, topic = pick_question(
                    "technical",
                    topics=DEFAULT_TECHNICAL_TOPICS,
                    exclude=exclude,
                    candidate_profile=candidate_profile,
                    question_index=i,
                )
                exclude.append(text)
                if topic == "resume_technologies":
                    found_resume_grounded = True
                    assert "Kubernetes" in text
            assert found_resume_grounded, "Expected at least one resume-grounded question in 6 draws"


class TestTopicPersistedThroughInterview:
    def test_technical_question_topic_is_persisted_and_visible_to_admin(self, client):
        _setup_institute(client, "tp1")
        student_resp = client.post(
            "/api/v1/institute/students",
            json={"name": "Student", "email": "tp1s1@students.example"},
        )
        student_id = student_resp.get_json()["data"]["id"]
        campaign_resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "TP Drive", "role": "Dev"}
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

        admin_view = client.get(f"/api/v1/institute/interviews/{interview_id}")
        data = admin_view.get_json()["data"]
        technical_round = next(r for r in data["rounds"] if r["round_type"] == "technical")
        assert len(technical_round["questions"]) > 0
        assert all(q["topic"] in DEFAULT_TECHNICAL_TOPICS for q in technical_round["questions"])
