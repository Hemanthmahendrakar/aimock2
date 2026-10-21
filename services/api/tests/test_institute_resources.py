from datetime import datetime, timezone
from app.extensions import db
from app.models import User, UserStatus


def _register_login(client, suffix="resources"):
    payload = {
        "institute_name": f"Institute {suffix}",
        "institute_email": f"admissions-{suffix}@example.test",
        "admin_full_name": "Test Admin",
        "admin_email": f"admin-{suffix}@example.test",
        "password": "SuperSecret123",
    }
    response = client.post("/api/v1/institute/auth/register", json=payload)
    assert response.status_code in (200, 201)
    user = User.query.filter_by(email=payload["admin_email"]).first()
    user.status = UserStatus.ACTIVE
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    login = client.post("/api/v1/institute/auth/login", json={"email": payload["admin_email"], "password": payload["password"]})
    assert login.status_code == 200


def test_resource_routes_are_registered(app):
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/institute/campuses" in paths
    assert "/api/v1/institute/companies" in paths
    assert "/api/v1/institute/question-bank" in paths


def test_campus_company_and_question_bank_crud(client):
    _register_login(client)
    campus = client.post("/api/v1/institute/campuses", json={"name": "Main Campus", "code": "MAIN"})
    assert campus.status_code == 201
    campus_id = campus.get_json()["data"]["id"]

    company = client.post("/api/v1/institute/companies", json={"name": "Example Systems", "website": "https://example.test"})
    assert company.status_code == 201
    company_id = company.get_json()["data"]["id"]

    question = client.post("/api/v1/institute/question-bank", json={
        "question": "Explain the difference between a process and a thread.",
        "round_type": "technical", "difficulty": "easy", "company_id": company_id,
        "expected_answer_criteria": "Discuss address space, scheduling, and resource sharing.",
    })
    assert question.status_code == 201
    question_id = question.get_json()["data"]["id"]
    assert client.get("/api/v1/institute/question-bank?round_type=technical").status_code == 200
    assert client.patch(f"/api/v1/institute/question-bank/{question_id}", json={"difficulty": "medium"}).status_code == 200
    assert client.delete(f"/api/v1/institute/question-bank/{question_id}").status_code == 200
    assert client.get("/api/v1/institute/campuses").get_json()["data"][0]["id"] == campus_id
