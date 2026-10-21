from datetime import datetime, timezone

from app.extensions import db
from app.models import User, UserStatus


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


def _create_student(client, email_suffix: str, name="Student"):
    resp = client.post(
        "/api/v1/institute/students",
        json={"name": name, "email": f"{email_suffix}@students.example"},
    )
    return resp.get_json()["data"]["id"]


class TestCreateCampaign:
    def test_create_with_defaults(self, client):
        _setup_institute(client, "ca1")
        resp = client.post(
            "/api/v1/institute/campaigns",
            json={"name": "SDE Drive 2027", "role": "Software Developer"},
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["status"] == "draft"
        assert data["difficulty"] == "medium"
        assert data["technical_duration_minutes"] == 15
        assert data["managerial_duration_minutes"] == 10
        assert data["hr_duration_minutes"] == 10
        assert data["assigned_student_count"] == 0

    def test_create_with_explicit_durations(self, client):
        _setup_institute(client, "ca2")
        resp = client.post(
            "/api/v1/institute/campaigns",
            json={
                "name": "Custom Drive",
                "role": "Backend Engineer",
                "technical_duration_minutes": 25,
                "difficulty": "hard",
                "question_categories": ["dsa", "dbms"],
            },
        )
        data = resp.get_json()["data"]
        assert data["technical_duration_minutes"] == 25
        assert data["difficulty"] == "hard"
        assert data["question_categories"] == ["dsa", "dbms"]

    def test_invalid_difficulty_rejected(self, client):
        _setup_institute(client, "ca3")
        resp = client.post(
            "/api/v1/institute/campaigns",
            json={"name": "X", "role": "Y", "difficulty": "impossible"},
        )
        assert resp.status_code == 422

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "X", "role": "Y"}
        )
        assert resp.status_code == 401


class TestUpdateCampaign:
    def test_update_fields(self, client):
        _setup_institute(client, "cu1")
        create_resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "Old Name", "role": "Dev"}
        )
        campaign_id = create_resp.get_json()["data"]["id"]

        resp = client.patch(
            f"/api/v1/institute/campaigns/{campaign_id}",
            json={"name": "New Name", "difficulty": "hard"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "New Name"
        assert data["difficulty"] == "hard"


class TestCampaignLifecycle:
    def _create(self, client):
        resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "Lifecycle Drive", "role": "Dev"}
        )
        return resp.get_json()["data"]["id"]

    def test_draft_to_active_to_completed(self, client):
        _setup_institute(client, "cl1")
        campaign_id = self._create(client)

        activate_resp = client.post(f"/api/v1/institute/campaigns/{campaign_id}/activate")
        assert activate_resp.status_code == 200
        assert activate_resp.get_json()["data"]["status"] == "active"

        complete_resp = client.post(f"/api/v1/institute/campaigns/{campaign_id}/complete")
        assert complete_resp.status_code == 200
        assert complete_resp.get_json()["data"]["status"] == "completed"

    def test_cannot_complete_a_draft_campaign(self, client):
        _setup_institute(client, "cl2")
        campaign_id = self._create(client)

        resp = client.post(f"/api/v1/institute/campaigns/{campaign_id}/complete")
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "invalid_status_transition"

    def test_cannot_transition_out_of_archived(self, client):
        _setup_institute(client, "cl3")
        campaign_id = self._create(client)
        client.post(f"/api/v1/institute/campaigns/{campaign_id}/archive")

        resp = client.post(f"/api/v1/institute/campaigns/{campaign_id}/activate")
        assert resp.status_code == 409

    def test_archive_reachable_from_active(self, client):
        _setup_institute(client, "cl4")
        campaign_id = self._create(client)
        client.post(f"/api/v1/institute/campaigns/{campaign_id}/activate")

        resp = client.post(f"/api/v1/institute/campaigns/{campaign_id}/archive")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "archived"


class TestRosterAssignment:
    def _create_campaign(self, client):
        resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "Roster Drive", "role": "Dev"}
        )
        return resp.get_json()["data"]["id"]

    def test_assign_students(self, client):
        _setup_institute(client, "ra1")
        campaign_id = self._create_campaign(client)
        s1 = _create_student(client, "ra1s1")
        s2 = _create_student(client, "ra1s2")

        resp = client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [s1, s2]},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["assigned"] == 2
        assert data["already_assigned"] == 0

        list_resp = client.get(f"/api/v1/institute/campaigns/{campaign_id}/students")
        assert list_resp.get_json()["data"]["pagination"]["total"] == 2

    def test_assigning_same_student_twice_is_idempotent(self, client):
        _setup_institute(client, "ra2")
        campaign_id = self._create_campaign(client)
        s1 = _create_student(client, "ra2s1")

        client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [s1]},
        )
        resp = client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [s1]},
        )
        data = resp.get_json()["data"]
        assert data["assigned"] == 0
        assert data["already_assigned"] == 1

    def test_assigning_nonexistent_student_id_reported_not_found(self, client):
        _setup_institute(client, "ra3")
        campaign_id = self._create_campaign(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        resp = client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [fake_id]},
        )
        data = resp.get_json()["data"]
        assert data["assigned"] == 0
        assert fake_id in data["not_found"]

    def test_unassign_student(self, client):
        _setup_institute(client, "ra4")
        campaign_id = self._create_campaign(client)
        s1 = _create_student(client, "ra4s1")
        client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [s1]},
        )

        resp = client.delete(f"/api/v1/institute/campaigns/{campaign_id}/students/{s1}")
        assert resp.status_code == 200

        list_resp = client.get(f"/api/v1/institute/campaigns/{campaign_id}/students")
        assert list_resp.get_json()["data"]["pagination"]["total"] == 0


class TestCampaignTenantIsolation:
    def test_cannot_assign_another_institutes_student_to_own_campaign(self, client):
        """
        Institute B creates a campaign, then tries to assign Institute
        A's student ID to it. Since assignment validates the student
        belongs to the CURRENT institute (not just that the ID exists
        somewhere), this must be reported as not_found, not succeed.
        """
        _setup_institute(client, "tca")
        student_a_id = _create_student(client, "tcas1")

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "tcb")
        campaign_resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "B's Drive", "role": "Dev"}
        )
        campaign_id = campaign_resp.get_json()["data"]["id"]

        resp = client.post(
            f"/api/v1/institute/campaigns/{campaign_id}/students",
            json={"student_ids": [student_a_id]},
        )
        data = resp.get_json()["data"]
        assert data["assigned"] == 0
        assert student_a_id in data["not_found"]

    def test_institute_b_cannot_read_institute_a_campaign(self, client):
        _setup_institute(client, "tcc")
        campaign_resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "A's Drive", "role": "Dev"}
        )
        campaign_id = campaign_resp.get_json()["data"]["id"]

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "tcd")

        resp = client.get(f"/api/v1/institute/campaigns/{campaign_id}")
        assert resp.status_code == 404

        list_resp = client.get("/api/v1/institute/campaigns")
        assert list_resp.get_json()["data"]["pagination"]["total"] == 0
