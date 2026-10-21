"""
Tests for Phase 12 (Institute Analytics). Interviews are pushed
straight to their target status/scores rather than run through the
full interview+evaluation flow (already covered end-to-end in
test_interview_engine.py / test_student_reports.py) — this file is
about aggregation correctness, not the interview lifecycle itself.

Ordering note: a student must be assigned to a campaign's roster
BEFORE the campaign is activated — activation only creates interviews
for whoever is already on the roster at that moment (assign_students
itself does not create interviews for an already-active campaign).
Every helper here assigns first, activates second.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    User, UserStatus, Interview, InterviewStatus, Evaluation,
)
from app.services.report_service import ReportService


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


def _create_campaign(client, suffix: str, *, role="Dev"):
    resp = client.post("/api/v1/institute/campaigns", json={"name": f"{suffix} Drive", "role": role})
    return resp.get_json()["data"]["id"]


def _create_student(client, suffix: str, *, department=None, batch=None):
    resp = client.post(
        "/api/v1/institute/students",
        json={
            "name": f"Student {suffix}",
            "email": f"{suffix}@students.example",
            "department": department,
            "batch": batch,
        },
    )
    return resp.get_json()["data"]["id"]


def _assign(client, campaign_id: str, student_id: str):
    client.post(
        f"/api/v1/institute/campaigns/{campaign_id}/students",
        json={"student_ids": [student_id]},
    )


def _activate(client, campaign_id: str):
    client.post(f"/api/v1/institute/campaigns/{campaign_id}/activate")


def _get_interview(campaign_id: str, student_id: str) -> Interview:
    import uuid as uuid_mod

    return (
        db.session.query(Interview)
        .filter(
            Interview.campaign_id == uuid_mod.UUID(campaign_id),
            Interview.student_id == uuid_mod.UUID(student_id),
        )
        .first()
    )


def _push_to_status(interview, *, status, started=False, completed=False):
    interview.status = status
    if started:
        interview.started_at = datetime.now(timezone.utc)
    if completed:
        interview.completed_at = datetime.now(timezone.utc)
    db.session.add(interview)
    db.session.commit()


def _create_report(app, interview, scores: dict, *, skill_gaps=None):
    """scores: {"technical": int, "managerial": int, "hr": int, "communication": int}"""
    with app.app_context():
        for dim, score in scores.items():
            db.session.add(
                Evaluation(
                    interview_id=interview.id,
                    dimension=dim,
                    score=score,
                    criteria_scores={"problem_solving": score} if dim == "technical" else {},
                    evidence=[], strengths=[], weaknesses=[], improvement_suggestions=[],
                    evaluation_source="heuristic_v1",
                )
            )
        db.session.commit()
        report = ReportService().generate_report(interview.id)
        if skill_gaps:
            report.current_version.technical_skill_gaps = skill_gaps
            db.session.commit()
    return report


class TestEmptyInstituteAnalytics:
    def test_zero_state_does_not_crash(self, client):
        _setup_institute(client, "an1")
        resp = client.get("/api/v1/institute/analytics")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total_students"] == 0
        assert data["assigned_interviews"] == 0
        assert data["completion_rate"] == 0.0
        assert data["average_score"] is None
        assert data["highest_score"] is None


class TestInterviewCounts:
    def test_counts_reflect_interview_progress(self, client, app):
        _setup_institute(client, "an2")
        campaign_id = _create_campaign(client, "an2")

        s1 = _create_student(client, "an2s1")
        s2 = _create_student(client, "an2s2")
        s3 = _create_student(client, "an2s3")
        for s in (s1, s2, s3):
            _assign(client, campaign_id, s)
        _activate(client, campaign_id)

        iv1 = _get_interview(campaign_id, s1)
        iv2 = _get_interview(campaign_id, s2)
        iv3 = _get_interview(campaign_id, s3)

        # iv1: still just invited. iv2: started. iv3: completed.
        _push_to_status(iv2, status=InterviewStatus.IN_PROGRESS, started=True)
        _push_to_status(iv3, status=InterviewStatus.COMPLETED, started=True, completed=True)

        resp = client.get("/api/v1/institute/analytics")
        data = resp.get_json()["data"]
        assert data["assigned_interviews"] == 3
        assert data["started_interviews"] == 2
        assert data["completed_interviews"] == 1
        assert data["completion_rate"] == round(1 / 3 * 100, 1)


class TestScoreStatsAndDistributions:
    def _setup_three_scored_interviews(self, client, app, suffix):
        _setup_institute(client, suffix)
        campaign_id = _create_campaign(client, suffix)

        students = [
            _create_student(client, f"{suffix}s{i}", department="CSE", batch="2027")
            for i in range(3)
        ]
        for s in students:
            _assign(client, campaign_id, s)
        _activate(client, campaign_id)

        interviews = [_get_interview(campaign_id, s) for s in students]
        for iv in interviews:
            _push_to_status(iv, status=InterviewStatus.COMPLETED, started=True, completed=True)

        _create_report(app, interviews[0], {"technical": 40, "managerial": 40, "hr": 40, "communication": 40})
        _create_report(app, interviews[1], {"technical": 70, "managerial": 70, "hr": 70, "communication": 70})
        _create_report(app, interviews[2], {"technical": 90, "managerial": 90, "hr": 90, "communication": 90})
        return interviews

    def test_score_stats(self, client, app):
        self._setup_three_scored_interviews(client, app, "an3")
        resp = client.get("/api/v1/institute/analytics")
        data = resp.get_json()["data"]
        assert data["average_score"] == round(200 / 3, 1)
        assert data["highest_score"] == 90
        assert data["lowest_score"] == 40
        assert data["scored_interviews"] == 3

    def test_readiness_distribution_buckets(self, client, app):
        self._setup_three_scored_interviews(client, app, "an4")
        resp = client.get("/api/v1/institute/analytics")
        dist = resp.get_json()["data"]["readiness_distribution"]
        assert dist["needs_improvement"] == 1  # score 40
        assert dist["ready"] == 1  # score 70
        assert dist["excellent"] == 1  # score 90
        assert dist["developing"] == 0

    def test_dimension_performance_averages(self, client, app):
        self._setup_three_scored_interviews(client, app, "an5")
        resp = client.get("/api/v1/institute/analytics")
        dims = resp.get_json()["data"]["dimension_performance"]
        expected = round((40 + 70 + 90) / 3, 1)
        assert dims["technical"] == expected
        assert dims["communication"] == expected

    def test_department_and_batch_performance(self, client, app):
        self._setup_three_scored_interviews(client, app, "an6")
        resp = client.get("/api/v1/institute/analytics")
        dept = resp.get_json()["data"]["department_performance"]
        assert len(dept) == 1
        assert dept[0]["name"] == "CSE"
        assert dept[0]["count"] == 3
        batch = resp.get_json()["data"]["batch_performance"]
        assert batch[0]["name"] == "2027"


class TestSkillGaps:
    def test_skill_gaps_tallied_across_reports(self, client, app):
        _setup_institute(client, "an7")
        campaign_id = _create_campaign(client, "an7")

        s1 = _create_student(client, "an7s1")
        s2 = _create_student(client, "an7s2")
        _assign(client, campaign_id, s1)
        _assign(client, campaign_id, s2)
        _activate(client, campaign_id)

        iv1 = _get_interview(campaign_id, s1)
        iv2 = _get_interview(campaign_id, s2)
        for iv in (iv1, iv2):
            _push_to_status(iv, status=InterviewStatus.COMPLETED, started=True, completed=True)

        _create_report(
            app, iv1, {"technical": 50, "managerial": 50, "hr": 50, "communication": 50},
            skill_gaps=["Weak on DBMS fundamentals", "Struggles with system design"],
        )
        _create_report(
            app, iv2, {"technical": 50, "managerial": 50, "hr": 50, "communication": 50},
            skill_gaps=["Weak on DBMS fundamentals"],
        )

        resp = client.get("/api/v1/institute/analytics")
        gaps = resp.get_json()["data"]["skill_gaps"]
        top = next(g for g in gaps if g["gap"] == "Weak on DBMS fundamentals")
        assert top["count"] == 2


class TestAnalyticsFilters:
    def test_filter_by_department(self, client, app):
        _setup_institute(client, "an8")
        campaign_id = _create_campaign(client, "an8")

        cse_student = _create_student(client, "an8cse", department="CSE")
        ece_student = _create_student(client, "an8ece", department="ECE")
        _assign(client, campaign_id, cse_student)
        _assign(client, campaign_id, ece_student)
        _activate(client, campaign_id)

        iv_cse = _get_interview(campaign_id, cse_student)
        iv_ece = _get_interview(campaign_id, ece_student)
        for iv in (iv_cse, iv_ece):
            _push_to_status(iv, status=InterviewStatus.COMPLETED, started=True, completed=True)

        resp = client.get("/api/v1/institute/analytics?department=CSE")
        data = resp.get_json()["data"]
        assert data["assigned_interviews"] == 1

    def test_filter_by_role(self, client, app):
        _setup_institute(client, "an9")
        campaign_a = _create_campaign(client, "an9a", role="Backend Engineer")
        campaign_b = _create_campaign(client, "an9b", role="Frontend Engineer")

        s1 = _create_student(client, "an9s1")
        s2 = _create_student(client, "an9s2")
        _assign(client, campaign_a, s1)
        _assign(client, campaign_b, s2)
        _activate(client, campaign_a)
        _activate(client, campaign_b)

        resp = client.get("/api/v1/institute/analytics?role=Backend%20Engineer")
        assert resp.get_json()["data"]["assigned_interviews"] == 1

    def test_invalid_date_rejected(self, client):
        _setup_institute(client, "an10")
        resp = client.get("/api/v1/institute/analytics?date_from=not-a-date")
        assert resp.status_code == 422

    def test_filter_options_returns_distinct_values(self, client):
        _setup_institute(client, "an11")
        _create_student(client, "an11s1", department="CSE", batch="2027")
        _create_student(client, "an11s2", department="ECE", batch="2027")

        resp = client.get("/api/v1/institute/analytics/filter-options")
        data = resp.get_json()["data"]
        assert set(data["departments"]) == {"CSE", "ECE"}
        assert data["batches"] == ["2027"]


class TestAnalyticsTenantIsolation:
    def test_institute_b_analytics_excludes_institute_a_data(self, client, app):
        _setup_institute(client, "ana")
        campaign_a = _create_campaign(client, "ana")
        s_a = _create_student(client, "anas1")
        _assign(client, campaign_a, s_a)
        _activate(client, campaign_a)

        iv_a = _get_interview(campaign_a, s_a)
        _push_to_status(iv_a, status=InterviewStatus.COMPLETED, started=True, completed=True)
        _create_report(app, iv_a, {"technical": 80, "managerial": 80, "hr": 80, "communication": 80})

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "anb")

        resp = client.get("/api/v1/institute/analytics")
        data = resp.get_json()["data"]
        assert data["assigned_interviews"] == 0
        assert data["average_score"] is None

    def test_requires_auth(self, client):
        resp = client.get("/api/v1/institute/analytics")
        assert resp.status_code == 401
