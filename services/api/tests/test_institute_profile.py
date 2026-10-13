"""
Institute profile/branding tests. Includes tenant isolation coverage,
matching the pattern established in test_tenant_isolation.py — these
routes have their own institute-scoped state, so isolation needs its
own explicit proof rather than relying on the dashboard test alone.
"""
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


class TestGetProfile:
    def test_requires_auth(self, client):
        resp = client.get("/api/v1/institute/profile")
        assert resp.status_code == 401

    def test_returns_own_profile(self, client):
        _register_and_activate(
            client,
            institute_name="Alpha Institute",
            institute_email="a@alpha.example",
            admin_email="admin@alpha.example",
            password="SuperSecret123",
        )
        _login(client, "admin@alpha.example", "SuperSecret123")

        resp = client.get("/api/v1/institute/profile")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Alpha Institute"


class TestUpdateProfile:
    def test_updates_fields(self, client):
        _register_and_activate(
            client,
            institute_name="Beta Institute",
            institute_email="a@beta.example",
            admin_email="admin@beta.example",
            password="SuperSecret123",
        )
        _login(client, "admin@beta.example", "SuperSecret123")

        resp = client.patch(
            "/api/v1/institute/profile",
            json={"phone": "+91-9000000000", "website": "https://beta.example"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["phone"] == "+91-9000000000"
        assert data["website"] == "https://beta.example"
        assert data["name"] == "Beta Institute"  # unspecified field untouched

    def test_invalid_website_rejected(self, client):
        _register_and_activate(
            client,
            institute_name="Gamma Institute",
            institute_email="a@gamma.example",
            admin_email="admin@gamma.example",
            password="SuperSecret123",
        )
        _login(client, "admin@gamma.example", "SuperSecret123")

        resp = client.patch(
            "/api/v1/institute/profile", json={"website": "not-a-url"}
        )
        assert resp.status_code == 422


class TestBranding:
    def test_update_branding_valid_colors(self, client):
        _register_and_activate(
            client,
            institute_name="Delta Institute",
            institute_email="a@delta.example",
            admin_email="admin@delta.example",
            password="SuperSecret123",
        )
        _login(client, "admin@delta.example", "SuperSecret123")

        resp = client.put(
            "/api/v1/institute/branding",
            json={"primary_color": "#1F6F5C", "secondary_color": "#E2A73B"},
        )
        assert resp.status_code == 200
        branding = resp.get_json()["data"]["branding"]
        assert branding["primary_color"] == "#1F6F5C"
        assert branding["secondary_color"] == "#E2A73B"

    def test_invalid_hex_color_rejected(self, client):
        _register_and_activate(
            client,
            institute_name="Epsilon Institute",
            institute_email="a@epsilon.example",
            admin_email="admin@epsilon.example",
            password="SuperSecret123",
        )
        _login(client, "admin@epsilon.example", "SuperSecret123")

        resp = client.put(
            "/api/v1/institute/branding", json={"primary_color": "not-a-color"}
        )
        assert resp.status_code == 422

    def test_branding_merges_not_overwrites(self, client):
        _register_and_activate(
            client,
            institute_name="Zeta Institute",
            institute_email="a@zeta.example",
            admin_email="admin@zeta.example",
            password="SuperSecret123",
        )
        _login(client, "admin@zeta.example", "SuperSecret123")

        client.put("/api/v1/institute/branding", json={"primary_color": "#111111"})
        resp = client.put(
            "/api/v1/institute/branding", json={"secondary_color": "#222222"}
        )
        branding = resp.get_json()["data"]["branding"]
        assert branding["primary_color"] == "#111111"
        assert branding["secondary_color"] == "#222222"


class TestProfileTenantIsolation:
    def test_institute_b_cannot_read_institute_a_profile_via_a_shared_session_model(
        self, client
    ):
        """
        There's no institute_id parameter anywhere in these routes to
        even attempt spoofing through — this test documents and
        confirms that: institute B's admin, authenticated, only ever
        sees/affects institute B's row.
        """
        _register_and_activate(
            client,
            institute_name="Institute A",
            institute_email="a@inst-a2.example",
            admin_email="admin@inst-a2.example",
            password="SuperSecret123",
        )
        _register_and_activate(
            client,
            institute_name="Institute B",
            institute_email="b@inst-b2.example",
            admin_email="admin@inst-b2.example",
            password="SuperSecret123",
        )

        _login(client, "admin@inst-b2.example", "SuperSecret123")
        resp = client.get("/api/v1/institute/profile")
        assert resp.get_json()["data"]["name"] == "Institute B"

        update_resp = client.patch(
            "/api/v1/institute/profile", json={"name": "Institute B Renamed"}
        )
        assert update_resp.get_json()["data"]["name"] == "Institute B Renamed"

        # Institute A's admin still sees Institute A, untouched.
        client.post("/api/v1/institute/auth/logout")
        _login(client, "admin@inst-a2.example", "SuperSecret123")
        resp_a = client.get("/api/v1/institute/profile")
        assert resp_a.get_json()["data"]["name"] == "Institute A"


class TestLogoUpload:
    _PNG_BYTES = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def test_rejects_missing_file(self, client):
        _register_and_activate(
            client,
            institute_name="Eta Institute",
            institute_email="a@eta.example",
            admin_email="admin@eta.example",
            password="SuperSecret123",
        )
        _login(client, "admin@eta.example", "SuperSecret123")

        resp = client.post("/api/v1/institute/logo", data={})
        assert resp.status_code == 422

    def test_rejects_non_image_bytes(self, client):
        _register_and_activate(
            client,
            institute_name="Theta Institute",
            institute_email="a@theta.example",
            admin_email="admin@theta.example",
            password="SuperSecret123",
        )
        _login(client, "admin@theta.example", "SuperSecret123")

        from io import BytesIO

        resp = client.post(
            "/api/v1/institute/logo",
            data={"file": (BytesIO(b"not an image, just text"), "fake.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_file"

    # NOTE: a real upload (valid PNG bytes going all the way through to
    # MinIO) needs the actual object store running, so it's exercised
    # manually per the README rather than in this offline test run.
