"""
Low-level security helpers: JWT encode/decode, secure random token
generation, and token hashing. No business logic here.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


def generate_raw_token(n_bytes: int = 32) -> str:
    """A cryptographically secure, URL-safe random token."""
    return secrets.token_urlsafe(n_bytes)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest. Used so the DB never holds a usable token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def encode_jwt(
    *,
    secret_key: str,
    algorithm: str,
    subject: str,
    ttl: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + ttl,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_jwt(*, token: str, secret_key: str, algorithm: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=[algorithm])
