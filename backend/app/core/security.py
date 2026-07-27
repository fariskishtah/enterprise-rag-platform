"""Password hashing and signed, expiring session tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from typing import Any

import bcrypt


def get_password_hash(password: str) -> str:
    """Return an adaptive bcrypt hash; plaintext passwords are never persisted."""

    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Passwords must not exceed 72 UTF-8 bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        encoded = plain_password.encode("utf-8")
        if len(encoded) > 72:
            return False
        return bcrypt.checkpw(encoded, hashed_password.encode("ascii"))
    except (TypeError, ValueError):
        return False


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(
    subject: str,
    secret_key: str,
    expires_delta: timedelta | None = None,
    role: str = "user",
    *,
    token_kind: str = "account",
    now: float | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    lifetime = int((expires_delta or timedelta(hours=24)).total_seconds())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "role": role,
        "kind": token_kind,
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "jti": secrets.token_urlsafe(12),
    }
    header_b64 = _encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(
        secret_key.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{header_b64}.{payload_b64}.{_encode(signature)}"


def decode_access_token(
    token: str,
    secret_key: str,
    *,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Validate a signed token and return its non-secret claims."""

    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        expected = hmac.new(
            secret_key.encode("utf-8"),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _decode(signature_b64)):
            return None
        header = json.loads(_decode(header_b64))
        payload = json.loads(_decode(payload_b64))
        current_time = int(time.time() if now is None else now)
        if header != {"alg": "HS256", "typ": "JWT"}:
            return None
        if not isinstance(payload, dict) or int(payload.get("exp", 0)) <= current_time:
            return None
        if int(payload.get("iat", current_time + 1)) > current_time:
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None
