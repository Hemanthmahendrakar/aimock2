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


SAMPLE_ROUNDS = [
    {
        "round_type": "technical",
        "duration_minutes": 20,
        "question_categories": ["dsa", "dbms"],
        "evaluation_criteria": {"correctness": 0.5, "depth": 0.5},
        "instructions": "Focus on data structures.",
    },
    {
        "round_type": "managerial",
        "duration_minutes": 8,
        "evaluation_criteria": {"ownership": 1.0},
    },
    {
        "round_type": "hr",
        "duration_minutes": 8,
        "instructions": "Assess motivation.",
    },
]


class TestCreateTemplate:
    def test_create_with_rounds(self, client):
        _setup_institute(client, "it1")
        resp = client.post(
            "/api/v1/institute/interview-templates",
            json={"name": "Standard SDE", "rounds": SAMPLE_ROUNDS},
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert len(data["rounds"]) == 3
        technical = next(r for r in data["rounds"] if r["round_type"] == "technical")
        assert technical["duration_minutes"] == 20
        assert technical["question_categories"] == ["dsa", "dbms"]

    def test_duplicate_round_type_rejected(self, client):
        _setup_institute(client, "it2")
        resp = client.post(
            "/api/v1/institute/interview-templates",
            json={
                "name": "Bad Template",
                "rounds": [
                    {"round_type": "technical", "duration_minutes": 10},
                    {"round_type": "technical", "duration_minutes": 15},
                ],
            },
        )
        assert resp.status_code == 422

    def test_duplicate_name_rejected(self, client):
        _setup_institute(client, "it3")
        client.post("/api/v1/institute/interview-templates", json={"name": "Dup Name"})
        resp = client.post("/api/v1/institute/interview-templates", json={"name": "Dup Name"})
        assert resp.status_code == 409

    def test_invalid_round_type_rejected(self, client):
        _setup_institute(client, "it4")
        resp = client.post(
            "/api/v1/institute/interview-templates",
            json={
                "name": "Bad Round",
                "rounds": [{"round_type": "coding_challenge", "duration_minutes": 10}],
            },
        )
        assert resp.status_code == 422


class TestDefaultTemplateExclusivity:
    def test_setting_new_default_unsets_old(self, client):
        _setup_institute(client, "id1")
        first = client.post(
            "/api/v1/institute/interview-templates",
            json={"name": "First", "is_default": True},
        ).get_json()["data"]
        second = client.post(
            "/api/v1/institute/interview-templates",
            json={"name": "Second", "is_default": True},
        ).get_json()["data"]

        assert second["is_default"] is True

        first_refetched = client.get(
            f"/api/v1/institute/interview-templates/{first['id']}"
        ).get_json()["data"]
        assert first_refetched["is_default"] is False

    def test_update_to_set_default(self, client):
        _setup_institute(client, "id2")
        a = client.post(
            "/api/v1/institute/interview-templates", json={"name": "A", "is_default": True}
        ).get_json()["data"]
        b = client.post(
            "/api/v1/institute/interview-templates", json={"name": "B"}
        ).get_json()["data"]

        client.patch(
            f"/api/v1/institute/interview-templates/{b['id']}", json={"is_default": True}
        )

        a_refetched = client.get(
            f"/api/v1/institute/interview-templates/{a['id']}"
        ).get_json()["data"]
        assert a_refetched["is_default"] is False


class TestTemplateUpdateAndDelete:
    def test_replace_rounds(self, client):
        _setup_institute(client, "iu1")
        template = client.post(
            "/api/v1/institute/interview-templates",
            json={"name": "Replaceable", "rounds": SAMPLE_ROUNDS},
        ).get_json()["data"]

        resp = client.patch(
            f"/api/v1/institute/interview-templates/{template['id']}",
            json={
                "rounds": [
                    {"round_type": "technical", "duration_minutes": 30},
                ]
            },
        )
        data = resp.get_json()["data"]
        assert len(data["rounds"]) == 1
        assert data["rounds"][0]["duration_minutes"] == 30

    def test_delete_soft_deletes(self, client):
        _setup_institute(client, "id3")
        template = client.post(
            "/api/v1/institute/interview-templates", json={"name": "To Delete"}
        ).get_json()["data"]

        del_resp = client.delete(
            f"/api/v1/institute/interview-templates/{template['id']}"
        )
        assert del_resp.status_code == 200

        get_resp = client.get(f"/api/v1/institute/interview-templates/{template['id']}")
        assert get_resp.status_code == 404


class TestTemplateTenantIsolation:
    def test_institute_b_cannot_read_institute_a_template(self, client):
        _setup_institute(client, "tta")
        template = client.post(
            "/api/v1/institute/interview-templates", json={"name": "A's Template"}
        ).get_json()["data"]

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "ttb")

        resp = client.get(f"/api/v1/institute/interview-templates/{template['id']}")
        assert resp.status_code == 404

    def test_same_template_name_allowed_across_institutes(self, client):
        _setup_institute(client, "ttc")
        resp_a = client.post(
            "/api/v1/institute/interview-templates", json={"name": "Shared Name"}
        )
        assert resp_a.status_code == 201

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "ttd")
        resp_b = client.post(
            "/api/v1/institute/interview-templates", json={"name": "Shared Name"}
        )
        assert resp_b.status_code == 201


class TestCampaignFromTemplate:
    def test_campaign_inherits_template_values(self, client):
        _setup_institute(client, "ct1")
        template = client.post(
            "/api/v1/institute/interview-templates",
            json={"name": "SDE Preset", "rounds": SAMPLE_ROUNDS},
        ).get_json()["data"]

        resp = client.post(
            "/api/v1/institute/campaigns",
            json={
                "name": "Drive From Template",
                "role": "SDE",
                "interview_template_id": template["id"],
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["technical_duration_minutes"] == 20
        assert data["managerial_duration_minutes"] == 8
        assert data["hr_duration_minutes"] == 8
        assert data["question_categories"] == ["dsa", "dbms"]
        assert data["technical_instructions"] == "Focus on data structures."
        assert data["hr_instructions"] == "Assess motivation."
        assert data["evaluation_criteria"]["technical"]["correctness"] == 0.5
        assert data["evaluation_criteria"]["managerial"]["ownership"] == 1.0
        assert data["interview_template_id"] == template["id"]

    def test_explicit_field_overrides_template(self, client):
        _setup_institute(client, "ct2")
        template = client.post(
            "/api/v1/institute/interview-templates",
            json={"name": "SDE Preset 2", "rounds": SAMPLE_ROUNDS},
        ).get_json()["data"]

        resp = client.post(
            "/api/v1/institute/campaigns",
            json={
                "name": "Drive Override",
                "role": "SDE",
                "interview_template_id": template["id"],
                "technical_duration_minutes": 45,
            },
        )
        data = resp.get_json()["data"]
        assert data["technical_duration_minutes"] == 45
        # Untouched fields still come from the template.
        assert data["managerial_duration_minutes"] == 8

    def test_campaign_without_template_still_uses_config_defaults(self, client):
        _setup_institute(client, "ct3")
        resp = client.post(
            "/api/v1/institute/campaigns", json={"name": "No Template Drive", "role": "SDE"}
        )
        data = resp.get_json()["data"]
        assert data["technical_duration_minutes"] == 15
        assert data["interview_template_id"] is None

    def test_cannot_use_another_institutes_template(self, client):
        _setup_institute(client, "ct4")
        template = client.post(
            "/api/v1/institute/interview-templates", json={"name": "A's Preset"}
        ).get_json()["data"]

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "ct5")

        resp = client.post(
            "/api/v1/institute/campaigns",
            json={
                "name": "B's Drive",
                "role": "SDE",
                "interview_template_id": template["id"],
            },
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "template_not_found"
