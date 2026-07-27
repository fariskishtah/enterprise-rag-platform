from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.middleware import (
    FixedWindowRateLimiter,
    RateLimitMiddleware,
    UploadConcurrencyMiddleware,
)
from app.document_processing.extraction import (
    ExtractedDocument,
    ExtractedSection,
    ExtractorRegistry,
)
from app.models.document import Document, DocumentType
from app.models.knowledge_base import KnowledgeBase
from app.services.cleanup import DemoCleanupService
from app.services.media import MediaProcessingService
from tests.helpers import create_knowledge_base, make_test_wav


def test_knowledge_base_and_file_quotas_are_terminal(
    client: TestClient,
    monkeypatch,
) -> None:
    client.app.state.settings.max_knowledge_bases = 1
    knowledge_base_id = create_knowledge_base(client)
    second = client.post("/api/v1/knowledge-bases", json={"name": "Second"})
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "knowledge_base_quota_exceeded"
    assert "cleanup" in second.json()["error"]["message"].lower()
    assert "remove an existing knowledge base" not in second.json()["error"]["message"].lower()

    client.app.state.settings.max_files_per_knowledge_base = 1
    first_file = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("first.txt", b"first source", "text/plain")},
    )
    second_file = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("second.txt", b"second source", "text/plain")},
    )
    assert first_file.status_code == 201
    assert second_file.status_code == 422
    assert second_file.json()["error"]["code"] == "knowledge_base_file_quota_exceeded"
    monkeypatch.setattr("app.services.media.validate_public_url", lambda value: value)
    linked = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media/from-url",
        json={"url": "https://media.example/source.mp4", "auto_process": False},
    )
    assert linked.status_code == 422
    assert linked.json()["error"]["code"] == "knowledge_base_file_quota_exceeded"


def test_request_body_upload_rate_and_media_size_limits_are_enforced(
    client: TestClient,
) -> None:
    body_limit = client.post(
        "/api/v1/knowledge-bases",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": "999999999"},
    )
    assert body_limit.status_code == 413
    assert body_limit.json()["error"]["code"] == "request_body_too_large"

    knowledge_base_id = create_knowledge_base(client)
    client.app.state.settings.upload_rate_limit_per_minute = 1
    first = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("first.txt", b"one", "text/plain")},
    )
    second = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("second.txt", b"two", "text/plain")},
    )
    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limit_exceeded"


def test_document_page_limit_stops_before_embedding(
    client: TestClient,
    knowledge_base_id: str,
    monkeypatch,
) -> None:
    client.app.state.settings.max_document_pages = 1
    extracted = ExtractedDocument(
        full_text="A bounded document.",
        sections=[
            ExtractedSection(
                section_index=0,
                text="A bounded document.",
                start_char=0,
                end_char=19,
                page_number=1,
            )
        ],
        page_count=2,
        character_count=19,
    )
    monkeypatch.setattr(ExtractorRegistry, "extract", lambda *_args: extracted)
    uploaded = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("pages.txt", b"A bounded document.", "text/plain")},
    ).json()
    client.post(f"/api/v1/documents/{uploaded['id']}/process")
    status = client.get(f"/api/v1/documents/{uploaded['id']}").json()

    assert status["status"] == "failed"
    assert "page limit" in status["status_message"].lower()
    assert status["indexed_chunk_count"] == 0


def test_media_upload_size_is_checked_before_processing(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    client.app.state.settings.max_media_upload_bytes = 8
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media",
        data={"auto_process": "false"},
        files={"file": ("audio.wav", make_test_wav(), "audio/wav")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "media_upload_too_large"


def test_media_mime_and_duration_limits_are_terminal(
    client: TestClient,
    monkeypatch,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    wrong_mime = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media",
        data={"auto_process": "false"},
        files={"file": ("audio.wav", make_test_wav(), "application/x-msdownload")},
    )
    assert wrong_mime.status_code == 415
    assert wrong_mime.json()["error"]["code"] == "unsupported_media_type"

    uploaded = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media",
        data={"auto_process": "false"},
        files={"file": ("long.wav", make_test_wav(frequency=220), "audio/wav")},
    ).json()
    client.app.state.settings.max_media_duration_seconds = 10
    monkeypatch.setattr(
        MediaProcessingService,
        "_probe_media",
        lambda *_args: {
            "format": {"duration": 11, "format_name": "wav"},
            "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le"}],
        },
    )
    queued = client.post(f"/api/v1/media/{uploaded['id']}/process")
    assert queued.status_code == 202
    failed = client.get(f"/api/v1/media/{uploaded['id']}").json()
    assert failed["status"] == "failed"
    assert failed["error_code"] == "media_duration_exceeded"
    assert "duration exceeds" in failed["safe_error_message"].lower()


def test_upload_concurrency_and_all_rate_limit_categories_are_bounded() -> None:
    settings = Settings(
        max_concurrent_uploads=1,
        login_max_attempts=2,
        upload_rate_limit_per_minute=1,
        generation_rate_limit_per_minute=1,
        transcription_rate_limit_per_minute=1,
        url_import_rate_limit_per_minute=1,
    )

    def request(path: str) -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [],
                "client": ("203.0.113.10", 1234),
                "server": ("testserver", 80),
            }
        )

    async def scenario() -> None:
        upload_middleware = UploadConcurrencyMiddleware(object(), settings)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def blocked(_: Request) -> Response:
            entered.set()
            await release.wait()
            return Response(status_code=200)

        first_upload = asyncio.create_task(
            upload_middleware.dispatch(
                request("/api/v1/knowledge-bases/kb/documents"), blocked
            )
        )
        await entered.wait()
        rejected = await upload_middleware.dispatch(
            request("/api/v1/knowledge-bases/kb/documents"), blocked
        )
        assert rejected.status_code == 429
        release.set()
        assert (await first_upload).status_code == 200

        rate_middleware = RateLimitMiddleware(object(), settings)

        async def accepted(_: Request) -> Response:
            return Response(status_code=200)

        paths = (
            ("/api/v1/auth/demo/login", 2),
            ("/api/v1/knowledge-bases/kb/documents", 1),
            ("/api/v1/knowledge-bases/kb/ask", 1),
            ("/api/v1/media/source/process", 1),
            ("/api/v1/knowledge-bases/kb/media/from-url", 1),
        )
        for path, limit in paths:
            for _ in range(limit):
                assert (
                    await rate_middleware.dispatch(request(path), accepted)
                ).status_code == 200
            assert (await rate_middleware.dispatch(request(path), accepted)).status_code == 429

        assert rate_middleware._category(request("/api/v1/evaluation/runs")) == (
            "generation",
            1,
        )
        assert rate_middleware._category(request("/api/v1/rag/warmup")) == (
            "generation",
            1,
        )

    asyncio.run(scenario())

    bounded = FixedWindowRateLimiter(max_keys=2)
    assert bounded.allow("first", 1)
    assert bounded.allow("second", 1)
    assert bounded.allow("third", 1)
    assert len(bounded._events) == 2


def test_cleanup_dry_run_expiry_protection_and_path_safety(
    client: TestClient,
    tmp_path: Path,
) -> None:
    settings = client.app.state.settings
    first_id = create_knowledge_base(client, "Expiring")
    uploaded = client.post(
        f"/api/v1/knowledge-bases/{first_id}/documents",
        files={"file": ("expired.txt", b"expired content", "text/plain")},
    ).json()
    stored_path: Path | None = None
    protected_id = create_knowledge_base(client, "Protected")
    outside = tmp_path / "outside.txt"
    outside.write_text("must survive", encoding="utf-8")

    past = datetime.now(UTC) - timedelta(hours=1)
    with client.app.state.session_factory() as session:
        expiring = session.get(KnowledgeBase, first_id)
        document = session.get(Document, uploaded["id"])
        protected = session.get(KnowledgeBase, protected_id)
        assert expiring is not None and document is not None and protected is not None
        stored_path = settings.storage_path / document.storage_key
        expiring.expires_at = past
        document.expires_at = past
        protected.expires_at = past
        protected.is_protected = True
        unsafe = Document(
            knowledge_base_id=protected_id,
            name="unsafe.txt",
            document_type=DocumentType.TXT,
            media_type="text/plain",
            size_bytes=1,
            checksum_sha256="f" * 64,
            storage_key="../outside.txt",
            expires_at=past,
        )
        session.add(unsafe)
        session.commit()
        unsafe_id = unsafe.id

    with client.app.state.session_factory() as session:
        dry_run = DemoCleanupService(session, settings).run(dry_run=True)
        assert session.get(KnowledgeBase, first_id) is not None
        assert session.get(KnowledgeBase, protected_id) is not None
        assert session.get(Document, unsafe_id) is not None
        assert dry_run.expired_records == 1

    assert stored_path is not None and stored_path.exists()
    assert outside.read_text(encoding="utf-8") == "must survive"

    with client.app.state.session_factory() as session:
        result = DemoCleanupService(session, settings).run(dry_run=False)
        assert session.get(KnowledgeBase, first_id) is None
        assert session.get(KnowledgeBase, protected_id) is not None
        assert session.get(Document, unsafe_id) is not None

    assert result.status == "ok"
    assert outside.read_text(encoding="utf-8") == "must survive"
    if stored_path is not None:
        assert not stored_path.exists()
