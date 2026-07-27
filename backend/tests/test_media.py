import os
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ProcessingError
from app.db.session import session_scope
from app.media.transcription import (
    FasterWhisperTranscriptionProvider,
    TranscribedSegment,
    TranscriptionProvider,
    TranscriptionResult,
)
from app.services.media import (
    YOUTUBE_COOKIE_EXPIRED_MESSAGE,
    YOUTUBE_COOKIE_REQUIRED_MESSAGE,
    YOUTUBE_FORMATS_UNAVAILABLE_MESSAGE,
    YOUTUBE_JAVASCRIPT_UNAVAILABLE_MESSAGE,
    YOUTUBE_PO_TOKEN_REQUIRED_MESSAGE,
    MediaProcessingService,
    deno_is_available,
)
from tests.helpers import create_knowledge_base, make_test_wav


@pytest.fixture
def ytdlp_runtime_cookie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    runtime_cookie = tmp_path / "runtime" / "youtube-cookies.txt"
    monkeypatch.setattr(
        "app.services.media.YTDLP_RUNTIME_COOKIE_FILE",
        runtime_cookie,
    )
    monkeypatch.setattr("app.services.media.deno_is_available", lambda: True)
    return runtime_cookie


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


class ArabicTranscriptionProvider(TranscriptionProvider):
    def __init__(self) -> None:
        self.languages: list[str | None] = []

    @property
    def model_name(self) -> str:
        return "deterministic-arabic-transcriber"

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        assert media_path.suffix == ".wav"
        self.languages.append(language)
        texts = [
            "مرحباً بكم في مراجعة المشروع.",
            "قرر الفريق إطلاق المنتج في 15 مايو 2026.",
            "يجب على مريم إكمال قائمة التحقق قبل يوم الخميس.",
        ]
        return TranscriptionResult(
            segments=[
                TranscribedSegment(
                    index=index,
                    start=float(index * 4),
                    end=float(index * 4 + 3),
                    text=text,
                    language="ar",
                    confidence=0.98,
                )
                for index, text in enumerate(texts)
            ],
            language="ar",
            language_probability=0.99,
            model_name=self.model_name,
        )


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


def test_arabic_transcription_preserves_language_punctuation_timestamps_and_order(
    client: TestClient,
) -> None:
    provider = ArabicTranscriptionProvider()
    client.app.state.transcription_provider = provider
    knowledge_base_id = create_knowledge_base(client)
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media",
        data={
            "auto_process": "true",
            "forced_language": "ar",
            "output_language": "ar",
        },
        files={"file": ("arabic.wav", make_test_wav(), "audio/wav")},
    )

    assert response.status_code == 201, response.text
    detail = client.get(f"/api/v1/media/{response.json()['id']}").json()
    transcript = client.get(f"/api/v1/media/{response.json()['id']}/transcript").json()
    intelligence = client.get(
        f"/api/v1/media/{response.json()['id']}/intelligence"
    ).json()
    assert detail["status"] == "ready"
    assert detail["transcript_jobs"][0]["forced_language"] == "ar"
    assert provider.languages == ["ar"]
    assert transcript["language"] == "ar"
    assert [segment["start_time"] for segment in transcript["segments"]] == [0.0, 4.0, 8.0]
    assert transcript["segments"][1]["text"].endswith(".")
    assert "15 مايو 2026" in transcript["full_text"]
    assert intelligence["output_language"] == "ar"
    assert intelligence["quiz_questions"][0].endswith("؟")
    assert intelligence["chapters"][0]["title"].startswith("مرحباً")


def test_faster_whisper_uses_cpu_bounded_beam_vad_and_transcription_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeWhisperModel:
        def transcribe(self, _path: str, **options: object):
            captured.update(options)
            segment = SimpleNamespace(
                start=0.0,
                end=2.0,
                text="نص عربي، مع علامات الترقيم.",
                avg_logprob=-0.1,
            )
            info = SimpleNamespace(language="ar", language_probability=0.99)
            return iter([segment]), info

    provider = FasterWhisperTranscriptionProvider(
        model_name="base",
        cache_path=tmp_path / "whisper",
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        num_workers=1,
        beam_size=3,
    )
    monkeypatch.setattr(provider, "_load_model", lambda: FakeWhisperModel())
    result = provider.transcribe(tmp_path / "arabic.wav", language="ar")

    assert captured == {
        "language": "ar",
        "task": "transcribe",
        "beam_size": 3,
        "vad_filter": True,
        "word_timestamps": False,
        "condition_on_previous_text": True,
    }
    assert result.segments[0].text == "نص عربي، مع علامات الترقيم."


def test_ytdlp_cookie_file_is_optional_readable_and_never_returned_by_api(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    ytdlp_runtime_cookie: Path,
) -> None:
    cookie_file = tmp_path / "youtube-cookies.txt"
    cookie_file.write_text("secret-cookie-line", encoding="utf-8")
    cookie_file.chmod(0o400)
    captured_options: list[dict[str, object]] = []

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.append(options)

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def extract_info(self, _url: str, *, download: bool):
            return {"id": "video", "title": "Safe video", "download": download}

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    configured = client.app.state.settings.model_copy(
        update={"ytdlp_cookies_file": cookie_file}
    )
    with session_scope(client.app.state.session_factory) as session:
        service = MediaProcessingService(
            session=session,
            storage=client.app.state.file_storage,
            settings=configured,
            embedding_provider=client.app.state.embedding_provider,
            transcription_provider=client.app.state.transcription_provider,
        )
        service._run_ytdlp(
            "https://www.youtube.com/watch?v=safe",
            {"skip_download": True},
            download=False,
            error_code="youtube_metadata_unavailable",
        )

    assert captured_options[0]["cookiefile"] == str(ytdlp_runtime_cookie)
    assert captured_options[0]["js_runtimes"] == {"deno": {"path": None}}
    assert captured_options[0]["no_warnings"] is False
    assert ytdlp_runtime_cookie.read_text(encoding="utf-8") == "secret-cookie-line"
    assert stat.S_IMODE(ytdlp_runtime_cookie.stat().st_mode) == 0o600
    assert stat.S_IMODE(cookie_file.stat().st_mode) == 0o400
    assert "secret-cookie-line" not in caplog.text
    configuration_text = client.get("/api/v1/rag/config").text
    assert str(cookie_file) not in configuration_text
    assert str(ytdlp_runtime_cookie) not in configuration_text
    assert "secret-cookie-line" not in configuration_text


@pytest.mark.parametrize("configured_path", [None, "missing", "unreadable"])
def test_ytdlp_omits_cookiefile_when_not_configured_or_not_readable(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_path: str | None,
    ytdlp_runtime_cookie: Path,
) -> None:
    del ytdlp_runtime_cookie
    captured_options: list[dict[str, object]] = []

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.append(options)

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def extract_info(self, _url: str, *, download: bool):
            return {"id": "video", "download": download}

    cookie_path: Path | None = None
    if configured_path == "missing":
        cookie_path = tmp_path / "missing-cookies.txt"
    elif configured_path == "unreadable":
        cookie_path = tmp_path / "unreadable-cookies.txt"
        cookie_path.write_text("secret", encoding="utf-8")
        original_access = __import__("os").access
        monkeypatch.setattr(
            "app.services.media.os.access",
            lambda path, mode: False if Path(path) == cookie_path else original_access(path, mode),
        )
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    settings = client.app.state.settings.model_copy(update={"ytdlp_cookies_file": cookie_path})
    with session_scope(client.app.state.session_factory) as session:
        service = MediaProcessingService(
            session=session,
            storage=client.app.state.file_storage,
            settings=settings,
            embedding_provider=client.app.state.embedding_provider,
            transcription_provider=client.app.state.transcription_provider,
        )
        service._run_ytdlp(
            "https://www.youtube.com/watch?v=safe",
            {},
            download=False,
            error_code="youtube_metadata_unavailable",
        )

    assert "cookiefile" not in captured_options[0]


def test_youtube_antibot_error_becomes_safe_terminal_failure_without_secrets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    ytdlp_runtime_cookie: Path,
) -> None:
    del ytdlp_runtime_cookie
    secret = "private-cookie-value"

    class FailingYoutubeDL:
        def __init__(self, _options: dict[str, object]) -> None:
            return

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def extract_info(self, _url: str, *, download: bool):
            del download
            raise RuntimeError(
                f"Sign in to confirm you're not a bot. Use --cookies for authentication {secret}"
            )

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FailingYoutubeDL))
    monkeypatch.setattr("app.services.media.validate_public_url", lambda value: value)
    knowledge_base_id = create_knowledge_base(client)
    linked = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media/from-url",
        json={
            "url": "https://www.youtube.com/watch?v=blocked",
            "auto_process": False,
        },
    )
    assert linked.status_code == 201, linked.text
    client.post(f"/api/v1/media/{linked.json()['id']}/process")
    failed = client.get(f"/api/v1/media/{linked.json()['id']}").json()

    assert failed["status"] == "failed"
    assert failed["error_code"] == "youtube_authentication_required"
    assert failed["safe_error_message"] == YOUTUBE_COOKIE_REQUIRED_MESSAGE
    assert secret not in str(failed)
    assert secret not in caplog.text


def test_runtime_cookie_refreshes_when_read_only_source_mtime_changes(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    ytdlp_runtime_cookie: Path,
) -> None:
    source = tmp_path / "youtube-secret.txt"
    source.write_text("first-secret-cookie", encoding="utf-8")
    source.chmod(0o400)
    observed_contents: list[str] = []

    class WritableCookieYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            self.cookie_file = Path(str(options["cookiefile"]))

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def extract_info(self, _url: str, *, download: bool):
            observed_contents.append(self.cookie_file.read_text(encoding="utf-8"))
            self.cookie_file.write_text("yt-dlp-runtime-update", encoding="utf-8")
            return {"id": "video", "download": download}

    monkeypatch.setitem(
        sys.modules,
        "yt_dlp",
        SimpleNamespace(YoutubeDL=WritableCookieYoutubeDL),
    )
    settings = client.app.state.settings.model_copy(update={"ytdlp_cookies_file": source})
    with session_scope(client.app.state.session_factory) as session:
        service = MediaProcessingService(
            session=session,
            storage=client.app.state.file_storage,
            settings=settings,
            embedding_provider=client.app.state.embedding_provider,
            transcription_provider=client.app.state.transcription_provider,
        )
        service._run_ytdlp(
            "https://www.youtube.com/watch?v=refresh",
            {},
            download=False,
            error_code="youtube_metadata_unavailable",
        )
        first_mtime = source.stat().st_mtime_ns
        source.chmod(0o600)
        source.write_text("second-secret-cookie", encoding="utf-8")
        os.utime(source, ns=(first_mtime + 1_000_000_000, first_mtime + 1_000_000_000))
        source.chmod(0o400)
        service._run_ytdlp(
            "https://www.youtube.com/watch?v=refresh",
            {},
            download=False,
            error_code="youtube_metadata_unavailable",
        )

    assert observed_contents == ["first-secret-cookie", "second-secret-cookie"]
    assert stat.S_IMODE(ytdlp_runtime_cookie.stat().st_mode) == 0o600
    assert "first-secret-cookie" not in caplog.text
    assert "second-secret-cookie" not in caplog.text


def test_ytdlp_jobs_are_serialized_and_use_audio_safe_format(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    ytdlp_runtime_cookie: Path,
) -> None:
    del ytdlp_runtime_cookie
    active = 0
    maximum_active = 0
    captured_formats: list[object] = []

    class ConcurrentYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_formats.append(options.get("format"))

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def extract_info(self, _url: str, *, download: bool):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            time.sleep(0.02)
            active -= 1
            return {"id": "video", "download": download}

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=ConcurrentYoutubeDL))
    with session_scope(client.app.state.session_factory) as session:
        service = MediaProcessingService(
            session=session,
            storage=client.app.state.file_storage,
            settings=client.app.state.settings,
            embedding_provider=client.app.state.embedding_provider,
            transcription_provider=client.app.state.transcription_provider,
        )

        def run() -> dict[str, object]:
            return service._run_ytdlp(
                "https://www.youtube.com/watch?v=concurrent",
                {},
                download=True,
                error_code="youtube_media_unavailable",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: run(), range(2)))

    assert len(results) == 2
    assert maximum_active == 1
    assert captured_formats == ["bestaudio/best", "bestaudio/best"]


def test_deno_availability_check_is_bounded_and_requires_a_working_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], int]] = []

    def successful_run(command: list[str], **options: object):
        calls.append((command, int(options["timeout"])))
        assert options["stdout"] is subprocess.DEVNULL
        assert options["stderr"] is subprocess.DEVNULL
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.media.shutil.which", lambda _name: "/runtime/deno")
    monkeypatch.setattr("app.services.media.subprocess.run", successful_run)
    assert deno_is_available() is True
    assert calls == [(["/runtime/deno", "--version"], 5)]

    monkeypatch.setattr("app.services.media.shutil.which", lambda _name: None)
    assert deno_is_available() is False


@pytest.mark.parametrize(
    ("diagnostic", "raised_detail", "expected_code", "expected_message"),
    [
        (
            "JS runtimes: none; n challenge solving failed for private-value",
            "Requested format is not available for private-value",
            "youtube_javascript_runtime_unavailable",
            YOUTUBE_JAVASCRIPT_UNAVAILABLE_MESSAGE,
        ),
        (
            "Only images are available for download",
            "Requested format is not available for private-value",
            "youtube_formats_unavailable",
            YOUTUBE_FORMATS_UNAVAILABLE_MESSAGE,
        ),
        (
            "This client requires a PO Token private-value",
            "No downloadable formats for private-value",
            "youtube_po_token_required",
            YOUTUBE_PO_TOKEN_REQUIRED_MESSAGE,
        ),
        (
            "The provided YouTube account cookies are no longer valid",
            "Cookies have expired private-value",
            "youtube_cookies_expired",
            YOUTUBE_COOKIE_EXPIRED_MESSAGE,
        ),
    ],
)
def test_youtube_challenge_failures_become_safe_terminal_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    ytdlp_runtime_cookie: Path,
    diagnostic: str,
    raised_detail: str,
    expected_code: str,
    expected_message: str,
) -> None:
    del ytdlp_runtime_cookie

    class FailingYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            self.logger = options["logger"]

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def extract_info(self, _url: str, *, download: bool):
            del download
            self.logger.warning(diagnostic)
            raise RuntimeError(raised_detail)

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FailingYoutubeDL))
    monkeypatch.setattr("app.services.media.validate_public_url", lambda value: value)
    knowledge_base_id = create_knowledge_base(client)
    linked = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/media/from-url",
        json={
            "url": "https://www.youtube.com/watch?v=challenge",
            "auto_process": False,
        },
    )
    assert linked.status_code == 201, linked.text
    queued = client.post(f"/api/v1/media/{linked.json()['id']}/process")
    assert queued.status_code == 202, queued.text
    failed = client.get(f"/api/v1/media/{linked.json()['id']}").json()

    assert failed["status"] == "failed"
    assert failed["error_code"] == expected_code
    assert failed["safe_error_message"] == expected_message
    assert "private-value" not in str(failed)
    assert "private-value" not in caplog.text
