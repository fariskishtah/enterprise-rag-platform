"""Security module for password hashing and JWT token creation/verification.

Provides standard library fallback for zero-dependency test safety.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def get_password_hash(password: str) -> str:
    salt = "enterprise_rag_salt_"
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_password_hash(plain_password) == hashed_password


def create_access_token(
    subject: str,
    secret_key: str = "enterprise_rag_jwt_secret_key",
    expires_delta: Any | None = None,
    role: str = "user",
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "role": role,
        "exp": int(time.time()) + 3600 * 24,
    }

    header_b64 = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    )
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )

    signature = hmac.new(
        secret_key.encode(),
        f"{header_b64}.{payload_b64}".encode(),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    return f"{header_b64}.{payload_b64}.{sig_b64}"
