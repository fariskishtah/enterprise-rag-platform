"""Run a deterministic local backend for browser-based product journeys."""

import hashlib
import math
import os
import shutil
import struct
import wave
from pathlib import Path

import uvicorn

from app.ai.providers.lightweight import (
    ExtractiveGenerationProvider,
    HashingEmbeddingProvider,
)
from app.core.config import Settings
from app.main import create_app
from app.media.transcription import (
    TranscribedSegment,
    TranscriptionProvider,
    TranscriptionResult,
)
from app.services import media as media_services
from app.services.media import MediaProcessingService


class BrowserFixtureTranscriber(TranscriptionProvider):
    @property
    def model_name(self) -> str:
        return "deterministic-browser-transcriber"

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        del media_path
        texts = [
            "The Atlas launch review is scheduled for Tuesday at 10 AM.",
            "Maya owns the deployment checklist and must finish it by Friday.",
            "The team agreed to use the blue release channel.",
            "The unresolved issue is the mobile authentication timeout.",
        ]
        return TranscriptionResult(
            segments=[
                TranscribedSegment(
                    index=index,
                    start=float(index * 5),
                    end=float(index * 5 + 4),
                    text=text,
                    language=language or "en",
                    confidence=0.98,
                )
                for index, text in enumerate(texts)
            ],
            language=language or "en",
            language_probability=0.99,
            model_name=self.model_name,
        )


def _browser_public_url(url: str) -> str:
    if url.startswith("https://media.example/"):
        return url
    return _original_validate_public_url(url)


def _browser_public_download(
    self: MediaProcessingService,
    source,
    temporary_directory: Path,
) -> Path:
    destination = temporary_directory / "linked-media.wav"
    sample_rate = 16_000
    frames = b"".join(
        struct.pack(
            "<h",
            round(math.sin(2 * math.pi * 440 * index / sample_rate) * 3_000),
        )
        for index in range(sample_rate)
    )
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)
    source.size_bytes = destination.stat().st_size
    source.checksum_sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
    source.media_type = "audio/wav"
    return destination


_original_validate_public_url = media_services.validate_public_url
media_services.validate_public_url = _browser_public_url
MediaProcessingService._download_public = _browser_public_download


def main() -> None:
    backend_root = Path(__file__).parents[1]
    runtime = backend_root / "data" / "playwright"
    if runtime.is_dir():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    frontend_port = os.getenv("PLAYWRIGHT_DEV_PORT", "5173")
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{runtime / 'playwright.db'}",
        storage_path=runtime / "uploads",
        model_cache_path=backend_root / "data" / "models",
        max_upload_bytes=2 * 1024 * 1024,
        max_media_upload_bytes=10 * 1024 * 1024,
        cors_origins=[f"http://127.0.0.1:{frontend_port}"],
        chunk_size=220,
        chunk_overlap=36,
        similarity_threshold=0,
        generation_temperature=0,
        generation_do_sample=False,
    )
    application = create_app(
        settings,
        embedding_provider=HashingEmbeddingProvider(dimension=384),
        generation_provider=ExtractiveGenerationProvider(),
        transcription_provider=BrowserFixtureTranscriber(),
    )
    uvicorn.run(application, host="127.0.0.1", port=8010, log_level="warning")


if __name__ == "__main__":
    main()
