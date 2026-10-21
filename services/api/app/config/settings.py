"""
Application configuration.

All secrets and environment-specific values MUST come from environment
variables. Never hardcode secrets here. See .env.example for the full
list of variables the app expects.
"""
import os
from datetime import timedelta


def _require_env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and set it."
        )
    return value


class BaseConfig:
    ENV = "base"
    DEBUG = False
    TESTING = False

    SECRET_KEY = _require_env("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = _require_env(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/mock_interview_dev",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", 10)),
    }

    REDIS_URL = _require_env("REDIS_URL", "redis://localhost:6379/0")

    # --- JWT / session settings ---
    JWT_ACCESS_TOKEN_TTL = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_TTL_MINUTES", 15))
    )
    JWT_REFRESH_TOKEN_TTL = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_TTL_DAYS", 7))
    )
    JWT_ALGORITHM = "HS256"

    ACCESS_COOKIE_NAME = "access_token"
    REFRESH_COOKIE_NAME = "refresh_token"
    COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
    COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")
    COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN") or None

    # --- Password reset token TTL ---
    PASSWORD_RESET_TTL = timedelta(
        minutes=int(os.environ.get("PASSWORD_RESET_TTL_MINUTES", 30))
    )

    # --- CORS ---
    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = REDIS_URL

    # --- Persistent local file storage ---
    FILE_STORAGE_ROOT = os.environ.get("FILE_STORAGE_ROOT", "/app/storage/uploads")

    # Retain this setting name for signed-link TTL compatibility.
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    S3_REGION = os.environ.get("S3_REGION", "")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL") or None
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
    S3_SIGNED_URL_TTL_SECONDS = int(os.environ.get("S3_SIGNED_URL_TTL_SECONDS", 3600))
    # boto3 needs "virtual-hosted" vs "path" addressing; path style is
    # required for MinIO/local dev, real AWS S3 works with either.
    S3_USE_PATH_STYLE = os.environ.get("S3_USE_PATH_STYLE", "true").lower() == "true"

    # --- Institute logo upload limits ---
    LOGO_MAX_SIZE_BYTES = int(os.environ.get("LOGO_MAX_SIZE_BYTES", 2 * 1024 * 1024))
    LOGO_ALLOWED_CONTENT_TYPES = ("image/png", "image/jpeg", "image/webp", "image/svg+xml")

    # --- Campaign round duration defaults (minutes) ---
    # Applied only when a campaign doesn't specify its own value at
    # creation time; each campaign then stores its own explicit number.
    # Never hardcode these elsewhere — read from here or from the
    # campaign row.
    TECHNICAL_ROUND_DEFAULT_MINUTES = int(
        os.environ.get("TECHNICAL_ROUND_DEFAULT_MINUTES", 15)
    )
    MANAGERIAL_ROUND_DEFAULT_MINUTES = int(
        os.environ.get("MANAGERIAL_ROUND_DEFAULT_MINUTES", 10)
    )
    HR_ROUND_DEFAULT_MINUTES = int(os.environ.get("HR_ROUND_DEFAULT_MINUTES", 10))

    # --- Resume upload limits ---
    RESUME_MAX_SIZE_BYTES = int(os.environ.get("RESUME_MAX_SIZE_BYTES", 5 * 1024 * 1024))
    RESUME_ALLOWED_CONTENT_TYPES = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    # --- Interview access / session tokens ---
    # The access token (in the invite link) is long-lived — a campaign
    # may be scheduled days or weeks out. The session JWT it's traded
    # for is scoped to a single interview and shorter-lived, covering
    # the lobby + the interview itself with headroom.
    INTERVIEW_ACCESS_TOKEN_TTL_DAYS = int(
        os.environ.get("INTERVIEW_ACCESS_TOKEN_TTL_DAYS", 14)
    )
    INTERVIEW_SESSION_TOKEN_TTL = timedelta(
        hours=int(os.environ.get("INTERVIEW_SESSION_TOKEN_TTL_HOURS", 3))
    )
    INTERVIEW_SESSION_COOKIE_NAME = "interview_session_token"

    # --- Celery / background jobs ---
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
    CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER

    # --- AI Gateway (used from Phase 8 onward, wired now) ---
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "none")
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-5")
    AI_API_BASE_URL = os.environ.get("AI_API_BASE_URL", "https://api.anthropic.com")
    AI_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("AI_REQUEST_TIMEOUT_SECONDS", 30))

    # --- Question Engine (Phase 8) ---
    # Initial batch size for a round; MAX is a hard safety cap on top of
    # it (initial batch + any adaptive follow-ups inserted afterward) so
    # a misbehaving AI provider can't generate follow-ups indefinitely.
    QUESTIONS_PER_ROUND_TARGET = int(os.environ.get("QUESTIONS_PER_ROUND_TARGET", 3))
    MAX_QUESTIONS_PER_ROUND = int(os.environ.get("MAX_QUESTIONS_PER_ROUND", 6))

    # --- Voice + Avatar (Phase 13) ---
    # All default to "none", which routes to a safe fallback rather than
    # a network call — see app/voice/*_provider.py. Setting these to a
    # real provider name activates the corresponding *_provider.py.
    STT_PROVIDER = os.environ.get("STT_PROVIDER", "none")  # none | whisper
    STT_API_KEY = os.environ.get("STT_API_KEY", "")
    STT_API_BASE_URL = os.environ.get("STT_API_BASE_URL", "https://api.openai.com")
    STT_MODEL = os.environ.get("STT_MODEL", "whisper-1")

    TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "none")  # none | elevenlabs
    TTS_API_KEY = os.environ.get("TTS_API_KEY", "")
    TTS_API_BASE_URL = os.environ.get("TTS_API_BASE_URL", "https://api.elevenlabs.io")
    TTS_DEFAULT_VOICE_ID = os.environ.get("TTS_DEFAULT_VOICE_ID", "")

    AVATAR_PROVIDER = os.environ.get("AVATAR_PROVIDER", "none")  # none | generic
    AVATAR_API_KEY = os.environ.get("AVATAR_API_KEY", "")
    AVATAR_API_BASE_URL = os.environ.get("AVATAR_API_BASE_URL", "")
    AVATAR_DEFAULT_ID = os.environ.get("AVATAR_DEFAULT_ID", "")

    VOICE_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("VOICE_REQUEST_TIMEOUT_SECONDS", 30))
    MAX_ANSWER_AUDIO_SIZE_BYTES = int(
        os.environ.get("MAX_ANSWER_AUDIO_SIZE_BYTES", 10 * 1024 * 1024)
    )

    # --- Observability ---
    SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
    POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY", "")

    # --- Mail (password reset and interview notifications only) ---
    MAIL_PROVIDER = os.environ.get("MAIL_PROVIDER", "console")  # console|ses|smtp
    MAIL_FROM_ADDRESS = os.environ.get("MAIL_FROM_ADDRESS", "no-reply@example.com")
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_SES_REGION = os.environ.get("MAIL_SES_REGION", "")


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    COOKIE_SECURE = False
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    # Flask-Limiter is Redis-backed (RATELIMIT_STORAGE_URI = REDIS_URL)
    # and keys by remote address, which is constant across every
    # Werkzeug test-client request. Left enabled, cumulative calls to a
    # rate-limited route across the WHOLE test session (e.g. /register
    # at "5 per hour", called 20+ times across the suite's test files)
    # would start failing with 429s that have nothing to do with the
    # test being run — a false failure, not a caught bug. Disabling
    # enforcement here tests the actual business logic; the limits
    # themselves are simple decorator config, not something that needs
    # a real Redis round-trip to verify per test run.
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/mock_interview_test",
    )


class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False
    COOKIE_SECURE = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None):
    env_name = env_name or os.environ.get("FLASK_ENV", "development")
    return CONFIG_MAP.get(env_name, DevelopmentConfig)
