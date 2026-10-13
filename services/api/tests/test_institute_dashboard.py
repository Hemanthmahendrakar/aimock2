from datetime import datetime, timezone

from app.extensions import db
from app.models import User, UserStatus


def _register_login(client, email="dashboard-admin@example.com"):
    client.post("/api/v1/institute/auth/register", json={
        "institute_name": "Dashboard Institute",
        "institute_email": "admissions-dashboard@example.com",
        "admin_full_name": "Dashboard Admin",
        "admin_email": email,
        "password": "SuperSecret123",
    })
    user = db.session.query(User).filter_by(email=email).first()
    user.status = UserStatus.ACTIVE
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return client.post("/api/v1/institute/auth/login", json={"email": email, "password": "SuperSecret123"})


def test_dashboard_returns_tenant_scoped_zero_state(client):
    _register_login(client)
    response = client.get("/api/v1/institute/dashboard")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["stats"]["total_students"] == 0
    assert data["stats"]["total_campaigns"] == 0
    assert data["stats"]["completion_rate"] == 0.0
    assert data["recent_campaigns"] == []


def test_dashboard_ignores_client_supplied_institute_id(client):
    _register_login(client, "dashboard-admin-2@example.com")
    response = client.get("/api/v1/institute/dashboard?institute_id=00000000-0000-0000-0000-000000000000")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["institute_id"] != "00000000-0000-0000-0000-000000000000"
