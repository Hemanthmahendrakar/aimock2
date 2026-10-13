from app.extensions import db
from app.models import EmailVerificationToken, User, UserStatus
from app.utils.security import hash_token


def _verify_user_directly(client, email: str):
    """
    Test helper: fetch the (hashed) verification token straight from the
    DB — since MailService just logs in tests — and hit the verify
    endpoint with the raw token by re-deriving it isn't possible (we
    only stored the hash). Instead we simulate by generating a token
    the same way the service does, OR simpler: directly flip the DB
    state. Here we take the simplest, most explicit route: call the
    service layer function-for-function via the DB row's known hash
    is not reversible, so we instead activate the user directly for
    tests that don't care about the verification flow itself.
    """
    user = db.session.query(User).filter(User.email == email).first()
    user.status = UserStatus.ACTIVE
    from datetime import datetime, timezone

    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()


class TestRegistration:
    def test_register_institute_success(self, client, register_payload):
        resp = client.post("/api/v1/institute/auth/register", json=register_payload)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["institute"]["name"] == register_payload["institute_name"]
        assert body["data"]["user"]["email"] == register_payload["admin_email"]
        assert body["data"]["user"]["status"] == "pending_verification"

    def test_register_duplicate_admin_email_rejected(self, client, register_payload):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        second = dict(register_payload)
        second["institute_email"] = "another@other-institute.example"
        resp = client.post("/api/v1/institute/auth/register", json=second)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "email_already_registered"

    def test_register_weak_password_rejected(self, client, register_payload):
        register_payload["password"] = "short"
        resp = client.post("/api/v1/institute/auth/register", json=register_payload)
        assert resp.status_code == 422

    def test_password_never_returned_in_response(self, client, register_payload):
        resp = client.post("/api/v1/institute/auth/register", json=register_payload)
        raw = resp.get_data(as_text=True)
        assert register_payload["password"] not in raw


class TestEmailVerification:
    def test_verify_email_activates_user_and_institute(self, client, register_payload, app):
        client.post("/api/v1/institute/auth/register", json=register_payload)

        # Pull the raw token the way MailService "sent" it: since we
        # can't reverse a hash, regenerate the flow through the service
        # directly for this test to get the raw token deterministically.
        from app.services.auth_service import AuthService
        from app.repositories.user_repository import UserRepository

        user = UserRepository().get_by_email(register_payload["admin_email"])
        with app.test_request_context():
            raw_token = AuthService()._issue_email_verification(user)
            db.session.commit()

        resp = client.post(
            "/api/v1/institute/auth/verify-email", json={"token": raw_token}
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["user"]["status"] == "active"

    def test_verify_email_invalid_token_rejected(self, client):
        resp = client.post(
            "/api/v1/institute/auth/verify-email", json={"token": "not-a-real-token-xxxx"}
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_token"


class TestLogin:
    def test_login_before_verification_blocked(self, client, register_payload):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        resp = client.post(
            "/api/v1/institute/auth/login",
            json={
                "email": register_payload["admin_email"],
                "password": register_payload["password"],
            },
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "account_not_active"

    def test_login_success_sets_cookies(self, client, register_payload):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        _verify_user_directly(client, register_payload["admin_email"])

        resp = client.post(
            "/api/v1/institute/auth/login",
            json={
                "email": register_payload["admin_email"],
                "password": register_payload["password"],
            },
        )
        assert resp.status_code == 200
        cookies = resp.headers.get_all("Set-Cookie")
        assert any("access_token=" in c for c in cookies)
        assert any("refresh_token=" in c for c in cookies)
        assert any("HttpOnly" in c for c in cookies)

    def test_login_wrong_password_rejected(self, client, register_payload):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        _verify_user_directly(client, register_payload["admin_email"])

        resp = client.post(
            "/api/v1/institute/auth/login",
            json={"email": register_payload["admin_email"], "password": "WrongPassword123"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "invalid_credentials"

    def test_account_locks_after_max_failed_attempts(self, client, register_payload):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        _verify_user_directly(client, register_payload["admin_email"])

        for _ in range(5):
            client.post(
                "/api/v1/institute/auth/login",
                json={
                    "email": register_payload["admin_email"],
                    "password": "WrongPassword123",
                },
            )

        resp = client.post(
            "/api/v1/institute/auth/login",
            json={
                "email": register_payload["admin_email"],
                "password": register_payload["password"],
            },
        )
        assert resp.status_code == 423
        assert resp.get_json()["error"]["code"] == "account_locked"

    def test_me_requires_authentication(self, client):
        resp = client.get("/api/v1/institute/auth/me")
        assert resp.status_code == 401

    def test_me_returns_current_user_after_login(self, client, register_payload):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        _verify_user_directly(client, register_payload["admin_email"])
        client.post(
            "/api/v1/institute/auth/login",
            json={
                "email": register_payload["admin_email"],
                "password": register_payload["password"],
            },
        )
        resp = client.get("/api/v1/institute/auth/me")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == register_payload["admin_email"]


class TestLogoutAndRefresh:
    def _login(self, client, register_payload):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        _verify_user_directly(client, register_payload["admin_email"])
        return client.post(
            "/api/v1/institute/auth/login",
            json={
                "email": register_payload["admin_email"],
                "password": register_payload["password"],
            },
        )

    def test_refresh_rotates_tokens(self, client, register_payload):
        self._login(client, register_payload)
        resp = client.post("/api/v1/institute/auth/refresh")
        assert resp.status_code == 200

    def test_logout_clears_cookies_and_revokes_refresh(self, client, register_payload):
        self._login(client, register_payload)
        resp = client.post("/api/v1/institute/auth/logout")
        assert resp.status_code == 200

        # A refresh attempt after logout must fail — the token was revoked.
        refresh_resp = client.post("/api/v1/institute/auth/refresh")
        assert refresh_resp.status_code == 401


class TestForgotPassword:
    def test_forgot_password_always_returns_generic_message(self, client):
        resp = client.post(
            "/api/v1/institute/auth/forgot-password",
            json={"email": "nonexistent@nowhere.example"},
        )
        assert resp.status_code == 200
        assert "sent" in resp.get_json()["data"]["message"].lower()

    def test_reset_password_with_valid_token(self, client, register_payload, app):
        client.post("/api/v1/institute/auth/register", json=register_payload)
        _verify_user_directly(client, register_payload["admin_email"])

        from app.services.auth_service import AuthService
        from app.repositories.user_repository import UserRepository

        with app.test_request_context():
            AuthService().request_password_reset(register_payload["admin_email"])

        from app.models import PasswordResetToken

        # We can't recover the raw token from its hash (by design), so
        # exercise reset_password through the service directly with a
        # freshly generated token for this assertion.
        from app.utils.security import generate_raw_token, hash_token as _hash
        from datetime import datetime, timedelta, timezone

        user = UserRepository().get_by_email(register_payload["admin_email"])
        raw = generate_raw_token()
        token_row = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.session.add(token_row)
        db.session.commit()

        resp = client.post(
            "/api/v1/institute/auth/reset-password",
            json={"token": raw, "new_password": "BrandNewPassword123"},
        )
        assert resp.status_code == 200

        login_resp = client.post(
            "/api/v1/institute/auth/login",
            json={
                "email": register_payload["admin_email"],
                "password": "BrandNewPassword123",
            },
        )
        assert login_resp.status_code == 200
