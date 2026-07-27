import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter


def test_liveness(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_detailed_readiness_and_protected_operations_status_are_safe(
    client: TestClient,
) -> None:
    readiness = client.get("/api/v1/readiness")
    operations = client.get(
        "/api/v1/operations/status",
        headers={"X-Request-ID": "health-test-request"},
    )

    assert readiness.status_code == 200
    assert all(readiness.json()["checks"].values())
    assert operations.status_code == 200
    assert operations.headers["x-request-id"] == "health-test-request"
    body = operations.json()
    assert body["heavy_operations"]["capacity"] == 1
    assert set(body["models"]) == {"embeddings", "generation", "transcription"}
    serialized = operations.text.lower()
    assert "session_secret" not in serialized
    assert "password_hash" not in serialized
    assert str(client.app.state.settings.storage_path).lower() not in serialized


def test_structured_request_fields_are_top_level_json_without_sensitive_values() -> None:
    record = logging.LogRecord(
        "enterprise_rag.requests",
        logging.INFO,
        __file__,
        1,
        "HTTP request completed",
        (),
        None,
    )
    record.enterprise_event = {
        "event": "http_request",
        "request_id": "request-123",
        "route": "/api/v1/health",
        "method": "GET",
        "status": 200,
        "duration_ms": 1.25,
    }
    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "http_request"
    assert payload["request_id"] == "request-123"
    assert payload["status"] == 200
    assert not {"password", "cookie", "authorization", "session_secret"} & payload.keys()
