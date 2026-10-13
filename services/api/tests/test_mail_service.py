import pytest
from app.services.mail_service import MailService


def test_console_mail_provider_logs_without_network(app, caplog):
    with app.app_context():
        app.config["MAIL_PROVIDER"] = "console"
        MailService().send_password_reset(to_email="student@example.test", reset_link="https://example.test/reset")
    assert "student@example.test" in caplog.text


def test_unknown_mail_provider_fails_clearly(app):
    with app.app_context():
        app.config["MAIL_PROVIDER"] = "not-a-provider"
        with pytest.raises(RuntimeError, match="Unsupported MAIL_PROVIDER"):
            MailService().send_password_reset(to_email="student@example.test", reset_link="https://example.test/reset")
