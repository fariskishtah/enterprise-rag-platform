from pathlib import Path

from fastapi.testclient import TestClient

from app.core.errors import ProcessingError
from app.media.transcription import (
    TranscribedSegment,
    TranscriptionProvider,
    TranscriptionResult,
)
from app.services.media import MediaProcessingService
from tests.helpers import create_knowledge_base, make_test_wav


class DeterministicTranscriptionProvider(TranscriptionProvider):
    @property
    def model_name(self) -> str:
        return "deterministic-test-transcriber"

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        assert media_path.suffix == ".wav"
        texts = [
            "The Atlas launch review is scheduled for Tuesday at 10 AM.",
            "Maya owns the deployment checklist and must finish it by Friday.",
            "The team agreed to use the blue release channel.",
            "The unresolved issue is the mobile authentication timeout.",
        ]
        segments = [
            TranscribedSegment(
                index=index,
                start=float(index * 5),
                end=float(index * 5 + 4),
                text=text,
                language=language or "en",
                confidence=0.97,
            )
            for index, text in enumerate(texts)
        ]
        return TranscriptionResult(
            segments=segments,
            language=language or "en",
            language_probability=0.99,
            model_name=self.model_name,
        )


class NoSpeechTranscriptionProvider(TranscriptionProvider):
    @property
    def model_name(self) -> str:
        return "no-speech-test-transcriber"

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        del media_path, language
        raise ProcessingError("No speech was detected in this media.", code="no_speech_detected")


def upload_media(
    client: TestClient,
    knowledge_base_id: str,
    *,
    filename: str = "review.wav",
    content: bytes | None = None,
    auto_process: bool = False,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media",
        data={"auto_process": str(auto_process).lower()},
        files={"file": (filename, content or make_test_wav(), "audio/wav")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_local_media_end_to_end_transcript_intelligence_qa_and_export(
    client: TestClient,
) -> None:
    client.app.state.transcription_provider = DeterministicTranscriptionProvider()
    knowledge_base_id = create_knowledge_base(client)
    media = upload_media(client, knowledge_base_id)

    queued = client.post(f"/api/v1/media/{media['id']}/process")
    assert queued.status_code == 202, queued.text
    ready = client.get(f"/api/v1/media/{media['id']}").json()
    assert ready["status"] == "ready"
    assert ready["segment_count"] == 4
    assert ready["has_summary"] is True
    assert ready["transcript_document_id"]

    transcript = client.get(f"/api/v1/media/{media['id']}/transcript").json()
    assert transcript["language"] == "en"
    assert transcript["segments"][0]["start_time"] == 0
    assert "Atlas launch review" in transcript["full_text"]

    intelligence = client.get(f"/api/v1/media/{media['id']}/intelligence").json()
    assert intelligence["short_summary"]
    assert intelligence["action_items"]
    assert "blue release channel" in " ".join(intelligence["decisions"])
    assert intelligence["unresolved_issues"]

    answer = client.post(
        f"/api/v1/media/{media['id']}/ask",
        json={"question": "Who owns the deployment checklist?"},
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert "Maya" in body["answer"]
    assert body["citations"][0]["timestamp_start"] == 5
    assert body["citations"][0]["passage"].startswith("Maya owns")
    assert body["not_found"] is False

    search = client.get(
        f"/api/v1/media/{media['id']}/transcript/search",
        params={"query": "authentication timeout"},
    ).json()
    assert search["total"] == 1
    assert search["results"][0]["segment"]["start_time"] == 15

    exported = client.get(f"/api/v1/media/{media['id']}/export/transcript.json")
    assert exported.status_code == 200
    assert exported.json()[1]["start"] == 5


def test_media_retry_is_idempotent(client: TestClient) -> None:
    client.app.state.transcription_provider = DeterministicTranscriptionProvider()
    knowledge_base_id = create_knowledge_base(client)
    media = upload_media(client, knowledge_base_id)
    client.post(f"/api/v1/media/{media['id']}/process")
    first = client.get(f"/api/v1/media/{media['id']}").json()
    first_chunks = client.get(f"/api/v1/documents/{first['transcript_document_id']}/chunks").json()
    client.post(f"/api/v1/media/{media['id']}/process")
    second = client.get(f"/api/v1/media/{media['id']}").json()

    assert first["segment_count"] == second["segment_count"] == 4
    assert first["transcript_document_id"] == second["transcript_document_id"]
    chunks = client.get(f"/api/v1/documents/{second['transcript_document_id']}/chunks").json()
    assert chunks["total"] == first_chunks["total"]
    assert chunks["total"] > 0


def test_media_validation_duplicate_private_url_corruption_and_no_speech(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    upload_media(client, knowledge_base_id)
    duplicate = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media",
        data={"auto_process": "false"},
        files={"file": ("same.wav", make_test_wav(), "audio/wav")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_media"

    private_url = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media/from-url",
        json={"url": "http://127.0.0.1/private.mp4"},
    )
    assert private_url.status_code == 422
    assert private_url.json()["error"]["code"] == "private_media_url"

    corrupt = upload_media(
        client,
        knowledge_base_id,
        filename="corrupt.mp4",
        content=b"not-a-video",
    )
    client.post(f"/api/v1/media/{corrupt['id']}/process")
    corrupt_status = client.get(f"/api/v1/media/{corrupt['id']}").json()
    assert corrupt_status["status"] == "failed"
    assert corrupt_status["error_code"] == "invalid_or_corrupt_media"
    assert corrupt_status["retryable"] is True

    client.app.state.transcription_provider = NoSpeechTranscriptionProvider()
    silent = upload_media(
        client,
        knowledge_base_id,
        filename="silent.wav",
        content=make_test_wav(frequency=220),
    )
    client.post(f"/api/v1/media/{silent['id']}/process")
    silent_status = client.get(f"/api/v1/media/{silent['id']}").json()
    assert silent_status["status"] == "failed"
    assert silent_status["error_code"] == "no_speech_detected"


def test_inaccessible_public_url_has_actionable_retryable_failure(
    client: TestClient,
    monkeypatch,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    monkeypatch.setattr(
        "app.services.media.validate_public_url",
        lambda value: value,
    )

    def unavailable_download(*_args, **_kwargs):
        raise ProcessingError(
            "The public media URL could not be accessed.",
            code="public_media_unavailable",
        )

    monkeypatch.setattr(MediaProcessingService, "_download_public", unavailable_download)
    linked = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media/from-url",
        json={
            "url": "https://media.example/unavailable.mp4",
            "auto_process": False,
        },
    )
    assert linked.status_code == 201, linked.text

    queued = client.post(f"/api/v1/media/{linked.json()['id']}/process")
    assert queued.status_code == 202, queued.text
    failed = client.get(f"/api/v1/media/{linked.json()['id']}").json()
    assert failed["status"] == "failed"
    assert failed["error_code"] == "public_media_unavailable"
    assert failed["retryable"] is True
