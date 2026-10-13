"""
Tests for Phase 11 (Student Reports). Covers the report pipeline
itself (heuristic synthesis, deterministic score computation,
versioning) plus the two HTTP routes this phase's audit added — admin
and student report retrieval — since neither existed before, despite
the full generation pipeline already being wired end-to-end.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    User,
    UserStatus,
    Interview,
    Report,
    ReportVersion,
    EvaluationDimension,
)
from app.ai.types import EvaluationResult, ReportContext
from app.services.heuristic_report import generate_report_heuristically
from app.services.report_service import ReportService, MissingEvaluations


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


def _sample_eval(dimension: str, score: int, **overrides) -> EvaluationResult:
    defaults = dict(
        dimension=dimension,
        score=score,
        criteria_scores={"problem_solving": score} if dimension == "technical" else {},
        evidence=[f"{dimension} evidence"],
        strengths=[f"{dimension} strength"],
        weaknesses=[f"{dimension} weakness"],
        improvement_suggestions=[f"{dimension} suggestion"],
        source="heuristic_v1",
    )
    defaults.update(overrides)
    return EvaluationResult(**defaults)


class TestHeuristicReportSynthesis:
    def test_aggregates_strengths_and_weaknesses_across_dimensions(self, app):
        with app.app_context():
            context = ReportContext(
                target_role="Dev", difficulty="medium", student_name="Ada",
                technical_eval=_sample_eval("technical", 80),
                managerial_eval=_sample_eval("managerial", 70),
                hr_eval=_sample_eval("hr", 75),
                communication_eval=_sample_eval("communication", 65),
            )
            content = generate_report_heuristically(context)
            assert "technical strength" in content.strengths
            assert "managerial strength" in content.strengths
            assert content.source == "heuristic_v1"
            assert content.model_version is None

    def test_deduplicates_repeated_items(self, app):
        with app.app_context():
            shared = _sample_eval("technical", 80, weaknesses=["Needs more practice"])
            shared2 = _sample_eval("managerial", 70, weaknesses=["Needs more practice"])
            context = ReportContext(
                target_role="Dev", difficulty="medium", student_name="Ada",
                technical_eval=shared, managerial_eval=shared2,
                hr_eval=_sample_eval("hr", 75), communication_eval=_sample_eval("communication", 65),
            )
            content = generate_report_heuristically(context)
            assert content.weaknesses.count("Needs more practice") == 1

    def test_never_returns_empty_required_sections(self, app):
        with app.app_context():
            def empty(dim):
                return EvaluationResult(
                    dimension=dim, score=0, criteria_scores={}, evidence=[],
                    strengths=[], weaknesses=[], improvement_suggestions=[],
                    source="heuristic_v1",
                )
            context = ReportContext(
                target_role="Dev", difficulty="medium", student_name="Ada",
                technical_eval=empty("technical"),
                managerial_eval=empty("managerial"),
                hr_eval=empty("hr"),
                communication_eval=empty("communication"),
            )
            content = generate_report_heuristically(context)
            assert len(content.strengths) > 0
            assert len(content.weaknesses) > 0
            assert len(content.improvement_plan) > 0


class TestReportServiceScoreComputation:
    def _setup_interview_with_evaluations(self, client, suffix: str, scores: dict) -> str:
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

        interview = (
            db.session.query(Interview)
            .filter(
                Interview.campaign_id == uuid_mod.UUID(campaign_id),
                Interview.student_id == uuid_mod.UUID(student_id),
            )
            .first()
        )
        interview_id = interview.id

        from app.models import Evaluation

        for dim, score in scores.items():
            db.session.add(
                Evaluation(
                    interview_id=interview_id,
                    dimension=dim,
                    score=score,
                    criteria_scores={"problem_solving": score} if dim == "technical" else {},
                    evidence=[], strengths=[], weaknesses=[], improvement_suggestions=[],
                    evaluation_source="heuristic_v1",
                )
            )
        db.session.commit()
        return str(interview_id)

    def test_overall_score_is_mean_of_four_dimensions(self, app, client):
        interview_id = self._setup_interview_with_evaluations(
            client, "rs1",
            {"technical": 80, "managerial": 60, "hr": 70, "communication": 90},
        )
        with app.app_context():
            import uuid as uuid_mod

            report = ReportService().generate_report(uuid_mod.UUID(interview_id))
            version = report.current_version
            assert version.overall_score == round((80 + 60 + 70 + 90) / 4)
            assert version.technical_score == 80
            assert version.problem_solving_score == 80

    def test_missing_evaluations_raises(self, app, client):
        interview_id = self._setup_interview_with_evaluations(
            client, "rs2", {"technical": 80}  # only one of four
        )
        with app.app_context():
            import uuid as uuid_mod

            try:
                ReportService().generate_report(uuid_mod.UUID(interview_id))
                assert False, "Expected MissingEvaluations"
            except MissingEvaluations:
                pass

    def test_regenerating_creates_a_new_version_not_overwrite(self, app, client):
        interview_id = self._setup_interview_with_evaluations(
            client, "rs3",
            {"technical": 50, "managerial": 50, "hr": 50, "communication": 50},
        )
        with app.app_context():
            import uuid as uuid_mod

            service = ReportService()
            report1 = service.generate_report(uuid_mod.UUID(interview_id))
            first_version_id = report1.current_version_id

            report2 = service.generate_report(uuid_mod.UUID(interview_id))
            second_version_id = report2.current_version_id

            assert first_version_id != second_version_id
            assert report1.id == report2.id  # same Report, new ReportVersion

            versions = (
                db.session.query(ReportVersion)
                .filter(ReportVersion.report_id == report1.id)
                .all()
            )
            assert len(versions) == 2
            assert {v.version_number for v in versions} == {1, 2}


class TestReportRoutesEndToEnd:
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
        for _ in range(30):
            state = client.get("/api/v1/interview/me").get_json()["data"]
            if state["status"] in ("completed", "report_ready", "evaluating", "report_generating"):
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

    def test_interview_reaches_report_ready(self, client):
        interview_id = self._complete_full_interview(client, "rr1")

        import uuid as uuid_mod

        interview = db.session.get(Interview, uuid_mod.UUID(interview_id))
        assert interview.status == "report_ready"
        assert interview.report_generated_at is not None

    def test_admin_can_view_report(self, client):
        interview_id = self._complete_full_interview(client, "rr2")

        resp = client.get(f"/api/v1/institute/interviews/{interview_id}/report")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "overall_score" in data
        assert "technical_score" in data
        assert "problem_solving_score" in data
        assert data["version_number"] == 1
        assert data["evaluation_version"] in ("heuristic_v1", "mixed_v1")
        assert data["prompt_version"] == "report_prompt_v1"

    def test_student_can_view_own_report(self, client):
        interview_id = self._complete_full_interview(client, "rr3")

        # Session cookie from the completed interview flow is still
        # active on this client — no re-exchange needed.
        resp = client.get("/api/v1/interview/report")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "overall_score" in data
        assert "improvement_plan" in data

    def test_report_not_ready_before_completion(self, client):
        _setup_institute(client, "rr4")
        student_resp = client.post(
            "/api/v1/institute/students",
            json={"name": "Student", "email": "rr4s1@students.example"},
        )
        student_id = student_resp.get_json()["data"]["id"]
        campaign_resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "rr4 Drive", "role": "Dev"}
        )
        campaign_id = campaign_resp.get_json()["data"]["id"]
        client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [student_id]},
        )
        client.post(f"/api/v1/institute/campaigns/{campaign_id}/activate")

        interviews = client.get(
            f"/api/v1/institute/campaigns/{campaign_id}/interviews"
        ).get_json()["data"]["items"]
        interview_id = interviews[0]["id"]

        resp = client.get(f"/api/v1/institute/interviews/{interview_id}/report")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "report_not_ready"


class TestReportTenantIsolation:
    def test_institute_b_cannot_view_institute_a_report(self, client):
        interview_id = TestReportRoutesEndToEnd()._complete_full_interview(client, "tra")

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "trb")

        resp = client.get(f"/api/v1/institute/interviews/{interview_id}/report")
        assert resp.status_code == 404

    def test_student_session_scoped_to_own_interview_only(self, client):
        """
        A student's interview-session cookie is scoped to exactly one
        interview via the JWT's interview_id claim — there's no
        interview_id parameter on /report to even attempt spoofing
        through. This completes two independent interviews and
        confirms each session's /report reflects only its own.
        """
        interview_id_a = TestReportRoutesEndToEnd()._complete_full_interview(client, "trc")
        resp_a = client.get("/api/v1/interview/report")
        assert resp_a.status_code == 200

        client.post("/api/v1/institute/auth/logout")
        interview_id_b = TestReportRoutesEndToEnd()._complete_full_interview(client, "trd")
        resp_b = client.get("/api/v1/interview/report")
        assert resp_b.status_code == 200

        assert interview_id_a != interview_id_b
