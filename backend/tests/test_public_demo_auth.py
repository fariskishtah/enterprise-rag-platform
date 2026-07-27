from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.ai.providers.lightweight import ExtractiveGenerationProvider, HashingEmbeddingProvider
from app.core.config import Settings
from app.core.security import create_access_token, get_password_hash
from app.main import create_app

DEMO_PASSWORD = "correct horse battery staple"
DEMO_HASH = get_password_hash(DEMO_PASSWORD)


def demo_client(tmp_path: Path, **overrides: object) -> TestClient:
    values: dict[str, object] = {
        "database_url": f"sqlite:///{tmp_path / 'auth.db'}",
        "storage_path": tmp_path / "uploads",
        "model_cache_path": tmp_path / "models",
        "langchain_index_path": tmp_path / "indexes",
        "access_mode": "demo_password",
        "demo_password_hash": DEMO_HASH,
        "session_secret": "a-secure-test-session-secret-that-is-long",
    }
    values.update(overrides)
    settings = Settings(**values)
    return TestClient(
        create_app(
            settings,
            embedding_provider=HashingEmbeddingProvider(),
            generation_provider=ExtractiveGenerationProvider(),
        )
    )


def test_demo_mode_protects_api_but_keeps_health_and_readiness_public(tmp_path: Path) -> None:
    with demo_client(tmp_path) as client:
        protected = client.get("/api/v1/knowledge-bases")
        health = client.get("/api/v1/health")
        readiness = client.get("/api/v1/readiness")
        configuration = client.get("/api/v1/auth/config")

    assert protected.status_code == 401
    assert protected.json()["error"]["code"] == "authentication_required"
    assert health.status_code == 200
    assert readiness.status_code == 200
    assert configuration.json() == {"mode": "demo_password", "session_expiry_minutes": 120}
    assert "hash" not in configuration.text.lower()
    assert "secret" not in configuration.text.lower()


def test_demo_login_uses_http_only_signed_session_and_logout_revokes_cookie(
    tmp_path: Path,
) -> None:
    with demo_client(tmp_path) as client:
        login = client.post("/api/v1/auth/demo/login", json={"password": DEMO_PASSWORD})
        session = client.get("/api/v1/auth/session")
        protected = client.get("/api/v1/knowledge-bases")
        logout = client.post("/api/v1/auth/logout")
        denied = client.get("/api/v1/knowledge-bases")

    cookie = login.headers["set-cookie"]
    assert login.status_code == 200
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert session.json()["authenticated"] is True
    assert protected.status_code == 200
    assert logout.status_code == 204
    assert "Max-Age=0" in logout.headers["set-cookie"]
    assert denied.status_code == 401


def test_secure_cookie_flag_and_generic_invalid_password_error(tmp_path: Path) -> None:
    with demo_client(tmp_path, cookie_secure=True) as client:
        invalid = client.post("/api/v1/auth/demo/login", json={"password": "wrong-password"})
        valid = client.post("/api/v1/auth/demo/login", json={"password": DEMO_PASSWORD})

    assert invalid.status_code == 401
    assert invalid.json()["error"] == {
        "code": "invalid_credentials",
        "message": "The sign-in details are invalid.",
    }
    assert DEMO_PASSWORD not in invalid.text
    assert "Secure" in valid.headers["set-cookie"]


def test_login_lockout_is_bounded_and_temporary(tmp_path: Path) -> None:
    with demo_client(tmp_path, login_max_attempts=2) as client:
        first = client.post("/api/v1/auth/demo/login", json={"password": "wrong-password"})
        second = client.post("/api/v1/auth/demo/login", json={"password": "wrong-password"})
        locked = client.post("/api/v1/auth/demo/login", json={"password": DEMO_PASSWORD})

    assert first.status_code == 401
    assert second.status_code == 429
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] in {
        "authentication_temporarily_locked",
        "rate_limit_exceeded",
    }


def test_expired_session_is_rejected(tmp_path: Path) -> None:
    secret = "a-secure-test-session-secret-that-is-long"
    expired = create_access_token(
        "public-demo",
        secret,
        expires_delta=timedelta(seconds=1),
        token_kind="demo",
        now=time.time() - 10,
    )
    with demo_client(tmp_path, session_secret=secret) as client:
        client.cookies.set("enterprise_rag_session", expired)
        response = client.get("/api/v1/knowledge-bases")

    assert response.status_code == 401


def test_open_development_mode_preserves_unauthenticated_local_access(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'open.db'}",
        storage_path=tmp_path / "uploads",
        access_mode="open",
    )
    with TestClient(
        create_app(
            settings,
            embedding_provider=HashingEmbeddingProvider(),
            generation_provider=ExtractiveGenerationProvider(),
        )
    ) as client:
        response = client.get("/api/v1/knowledge-bases")
        session = client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert session.json()["authenticated"] is True


def test_accounts_mode_boundary_preserves_existing_registration_and_login(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'accounts.db'}",
        storage_path=tmp_path / "uploads",
        access_mode="accounts",
        session_secret="a-secure-accounts-session-secret-that-is-long",
    )
    with TestClient(
        create_app(
            settings,
            embedding_provider=HashingEmbeddingProvider(),
            generation_provider=ExtractiveGenerationProvider(),
        )
    ) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": "demo@example.com",
                "password": "a-long-account-password",
                "full_name": "Demo User",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "demo@example.com", "password": "a-long-account-password"},
        )
        protected = client.get("/api/v1/knowledge-bases")

    assert registered.status_code == 201
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    assert protected.status_code == 200
