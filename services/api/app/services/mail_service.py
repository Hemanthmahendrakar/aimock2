"""Mail delivery abstraction: console (development), SMTP, or AWS SES."""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger("app.mail")

class MailService:
    def send_email_verification(self, *, to_email: str, verification_link: str) -> None:
        self._send(to_email=to_email, subject="Verify your institute account", body=f"Click to verify your account: {verification_link}")

    def send_password_reset(self, *, to_email: str, reset_link: str) -> None:
        self._send(to_email=to_email, subject="Reset your password", body=f"Click to reset your password: {reset_link}")

    def send_interview_invitation(self, *, to_email: str, student_name: str, role: str, interview_link: str) -> None:
        self._send(to_email=to_email, subject=f"Your mock interview for {role} is ready", body=f"Hi {student_name},\n\nYour mock interview for the {role} role is ready. Open this link when you're ready to begin:\n{interview_link}\n\nGood luck!")

    def _send(self, *, to_email: str, subject: str, body: str) -> None:
        provider = str(current_app.config.get("MAIL_PROVIDER", "console")).lower()
        sender = current_app.config.get("MAIL_FROM_ADDRESS", "no-reply@example.com")
        if provider == "console":
            logger.info("EMAIL to=%s subject=%s body=%s", to_email, subject, body)
            return
        if provider == "smtp":
            self._send_smtp(sender, to_email, subject, body)
            return
        if provider == "ses":
            self._send_ses(sender, to_email, subject, body)
            return
        raise RuntimeError(f"Unsupported MAIL_PROVIDER '{provider}'. Choose console, smtp, or ses.")

    @staticmethod
    def _send_smtp(sender: str, recipient: str, subject: str, body: str) -> None:
        host = current_app.config.get("SMTP_HOST")
        port = int(current_app.config.get("SMTP_PORT", 587))
        username = current_app.config.get("SMTP_USERNAME")
        password = current_app.config.get("SMTP_PASSWORD")
        use_tls = bool(current_app.config.get("SMTP_USE_TLS", True))
        if not host:
            raise RuntimeError("SMTP_HOST is required when MAIL_PROVIDER=smtp")
        msg = EmailMessage(); msg["From"] = sender; msg["To"] = recipient; msg["Subject"] = subject; msg.set_content(body)
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password or "")
            server.send_message(msg)

    @staticmethod
    def _send_ses(sender: str, recipient: str, subject: str, body: str) -> None:
        import boto3
        region = current_app.config.get("MAIL_SES_REGION") or current_app.config.get("S3_REGION") or "us-east-1"
        boto3.client("ses", region_name=region).send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": {"Text": {"Data": body, "Charset": "UTF-8"}}},
        )
