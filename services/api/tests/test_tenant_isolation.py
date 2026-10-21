"""
These tests exist to prove the core multi-tenant guarantee: an
authenticated user from Institute A can never act with Institute B's
institute_id, no matter what the client sends. The backend must derive
institute scope solely from the authenticated session.
"""
from app.extensions import db
from app.models import User, UserStatus
from datetime import datetime, timezone


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


class TestTenantIsolation:
    def test_dashboard_returns_only_own_institute_id(self, client):
        user_a = _register_and_activate(
            client,
            institute_name="Institute A",
            institute_email="a@inst-a.example",
            admin_email="admin@inst-a.example",
            password="SuperSecret123",
        )
        client.post(
            "/api/v1/institute/auth/login",
            json={"email": "admin@inst-a.example", "password": "SuperSecret123"},
        )

        resp = client.get("/api/v1/institute/dashboard")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["institute_id"] == str(user_a.institute_id)

    def test_client_supplied_institute_id_is_ignored(self, client):
        """
        Even if a malicious/buggy client sends a different institute_id
        (query param, header, or body), the dashboard must still resolve
        to the authenticated user's own institute — because the route
        never reads institute_id from the request at all.
        """
        user_a = _register_and_activate(
            client,
            institute_name="Institute A",
            institute_email="a2@inst-a.example",
            admin_email="admin2@inst-a.example",
            password="SuperSecret123",
        )
        user_b = _register_and_activate(
            client,
            institute_name="Institute B",
            institute_email="b@inst-b.example",
            admin_email="admin@inst-b.example",
            password="SuperSecret123",
        )
        assert user_a.institute_id != user_b.institute_id

        client.post(
            "/api/v1/institute/auth/login",
            json={"email": "admin2@inst-a.example", "password": "SuperSecret123"},
        )

        # Attempt to spoof Institute B's id via query string — the route
        # doesn't even look at it, but we assert the response proves it.
        resp = client.get(
            f"/api/v1/institute/dashboard?institute_id={user_b.institute_id}"
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["institute_id"] == str(user_a.institute_id)
        assert resp.get_json()["data"]["institute_id"] != str(user_b.institute_id)

    def test_institute_b_admin_cannot_use_institute_a_session(self, client):
        """
        Sanity check: logging in as B's admin never yields A's
        institute_id, confirming token->user->institute resolution is
        per-session, not global state leaking across requests.
        """
        _register_and_activate(
            client,
            institute_name="Institute A",
            institute_email="a3@inst-a.example",
            admin_email="admin3@inst-a.example",
            password="SuperSecret123",
        )
        user_b = _register_and_activate(
            client,
            institute_name="Institute B",
            institute_email="b2@inst-b.example",
            admin_email="admin2@inst-b.example",
            password="SuperSecret123",
        )

        client.post(
            "/api/v1/institute/auth/login",
            json={"email": "admin2@inst-b.example", "password": "SuperSecret123"},
        )
        resp = client.get("/api/v1/institute/dashboard")
        assert resp.get_json()["data"]["institute_id"] == str(user_b.institute_id)

    def test_unauthenticated_request_cannot_reach_dashboard(self, client):
        resp = client.get("/api/v1/institute/dashboard")
        assert resp.status_code == 401
