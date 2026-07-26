from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.ai.interfaces import EmbeddingProvider
from app.ai.vectorstores.relational import RelationalVectorStore
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ProcessingError, UploadValidationError
from app.document_processing.chunking import TextChunker
from app.document_processing.extraction import ExtractedSection
from app.media.intelligence import TranscriptIntelligenceService
from app.media.transcription import (
    TranscribedSegment,
    TranscriptionProvider,
    stable_segment_id,
    subtitle_segments,
)
from app.media.validation import is_youtube_url, validate_media_filename, validate_public_url
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentSection,
    DocumentStatus,
    DocumentType,
)
from app.models.media import (
    MediaChapter,
    MediaProcessingAttempt,
    MediaProcessingStatus,
    MediaSource,
    MediaSourceKind,
    MediaSummary,
    TranscriptJob,
    TranscriptJobStatus,
    TranscriptSegment,
)
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.repositories.media import MediaRepository
from app.services.language import resolve_output_language, transcription_language
from app.services.storage import LocalFileStorage

STAGE_NUMBER = {
    MediaProcessingStatus.UPLOADED_OR_LINKED: 0,
    MediaProcessingStatus.VALIDATING: 1,
    MediaProcessingStatus.FETCHING_METADATA: 2,
    MediaProcessingStatus.DOWNLOADING_OR_EXTRACTING_SUBTITLES: 3,
    MediaProcessingStatus.EXTRACTING_AUDIO: 4,
    MediaProcessingStatus.TRANSCRIBING: 5,
    MediaProcessingStatus.TRANSCRIPT_READY: 6,
    MediaProcessingStatus.CHUNKING: 7,
    MediaProcessingStatus.EMBEDDING: 8,
    MediaProcessingStatus.INDEXING: 9,
    MediaProcessingStatus.SUMMARISING: 10,
    MediaProcessingStatus.READY: 11,
    MediaProcessingStatus.FAILED: 0,
}

YOUTUBE_COOKIE_REQUIRED_MESSAGE = (
    "YouTube requires authenticated cookies on this server. Update the server cookie file "
    "or upload the media file directly."
)
YOUTUBE_AUTH_PATTERNS = (
    "sign in to confirm you’re not a bot",
    "sign in to confirm you're not a bot",
    "cookies-from-browser",
    "cookies for authentication",
    "login required",
)


class _SilentYtdlpLogger:
    """Prevent yt-dlp diagnostics from printing URLs, headers, or cookie details."""

    def debug(self, _message: str) -> None:
        return

    def warning(self, _message: str) -> None:
        return

    def error(self, _message: str) -> None:
        return


class MediaIngestionService:
    def __init__(
        self,
        *,
        session: Session,
        storage: LocalFileStorage,
        settings: Settings,
    ) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        self.media = MediaRepository(session)

    async def upload(self, knowledge_base_id: str, upload: UploadFile) -> MediaSource:
        self._require_knowledge_base(knowledge_base_id)
        original_name = Path(upload.filename or "").name
        if not original_name:
            raise UploadValidationError(
                code="missing_filename", message="The uploaded media must have a filename."
            )
        extension, media_type = validate_media_filename(original_name)
        media_id = str(uuid.uuid4())
        relative_key = Path(knowledge_base_id) / "media" / f"{media_id}{extension}"
        destination = self.storage.root / relative_key
        temporary = destination.with_suffix(destination.suffix + ".uploading")
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary.open("xb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_media_upload_bytes:
                        raise UploadValidationError(
                            code="media_upload_too_large",
                            message=(
                                "Media may not exceed "
                                f"{self.settings.max_media_upload_bytes} bytes."
                            ),
                            status_code=413,
                        )
                    digest.update(chunk)
                    output.write(chunk)
            if size == 0:
                raise UploadValidationError(
                    code="empty_media", message="The uploaded media is empty."
                )
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        checksum = digest.hexdigest()
        duplicate = self.media.find_by_checksum(knowledge_base_id, checksum)
        if duplicate is not None:
            destination.unlink(missing_ok=True)
            raise ConflictError(
                code="duplicate_media",
                message=f"This media is already stored as '{duplicate.title}'.",
            )
        source = MediaSource(
            id=media_id,
            knowledge_base_id=knowledge_base_id,
            source_kind=MediaSourceKind.UPLOAD,
            storage_key=relative_key.as_posix(),
            original_filename=original_name,
            media_type=media_type,
            size_bytes=size,
            checksum_sha256=checksum,
            source_platform="local_upload",
            title=Path(original_name).stem,
            status=MediaProcessingStatus.UPLOADED_OR_LINKED,
            status_message="Stored securely and queued for validation.",
        )
        return self.media.add(source)

    def create_url(self, knowledge_base_id: str, url: str, title: str | None = None) -> MediaSource:
        self._require_knowledge_base(knowledge_base_id)
        safe_url = validate_public_url(url)
        duplicate = self.media.find_by_url(knowledge_base_id, safe_url)
        if duplicate is not None:
            raise ConflictError(
                code="duplicate_media_url",
                message=f"This URL is already linked as '{duplicate.title}'.",
            )
        youtube = is_youtube_url(safe_url)
        source = MediaSource(
            knowledge_base_id=knowledge_base_id,
            source_kind=(MediaSourceKind.YOUTUBE if youtube else MediaSourceKind.PUBLIC_URL),
            original_url=safe_url,
            source_platform="youtube" if youtube else "public_web",
            title=title or ("YouTube video" if youtube else "Linked media"),
            status=MediaProcessingStatus.UPLOADED_OR_LINKED,
            status_message="Linked and queued for safe metadata retrieval.",
        )
        return self.media.add(source)

    def delete(self, media_source_id: str) -> None:
        source = self.media.get(media_source_id)
        if source is None:
            raise NotFoundError("Media source")
        if source.storage_key:
            self.storage.delete(source.storage_key)
        if source.transcript_document_id:
            document = DocumentRepository(self.session).get(source.transcript_document_id)
            if document is not None:
                transcript_storage_key = document.storage_key
                DocumentRepository(self.session).delete(document)
                self.storage.delete(transcript_storage_key)
        self.media.delete(source)

    def _require_knowledge_base(self, knowledge_base_id: str) -> None:
        if KnowledgeBaseRepository(self.session).get(knowledge_base_id) is None:
            raise NotFoundError("Knowledge base")


class MediaProcessingService:
    def __init__(
        self,
        *,
        session: Session,
        storage: LocalFileStorage,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        transcription_provider: TranscriptionProvider,
    ) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.transcription_provider = transcription_provider
        self.media = MediaRepository(session)
        self.documents = DocumentRepository(session)
        self.vector_store = RelationalVectorStore(session)
        self.intelligence = TranscriptIntelligenceService()

    def process(
        self,
        media_source_id: str,
        *,
        forced_language: str | None = None,
        output_language: str = "auto",
    ) -> MediaSource:
        source = self.media.get(media_source_id)
        if source is None:
            raise NotFoundError("Media source")
        source.processing_attempts += 1
        source.error_code = None
        source.safe_error_message = None
        source.technical_error_message = None
        source.retryable = False
        source.failed_at = None
        attempt = MediaProcessingAttempt(
            media_source_id=source.id,
            attempt_number=source.processing_attempts,
            started_at=datetime.now(UTC),
        )
        self.session.add(attempt)
        self.session.commit()

        temporary_root = self.storage.root / ".processing"
        temporary_root.mkdir(parents=True, exist_ok=True)
        temporary_directory = Path(tempfile.mkdtemp(prefix=f"{source.id}-", dir=temporary_root))
        active_job: TranscriptJob | None = None
        try:
            self._status(source, MediaProcessingStatus.VALIDATING, "Validating media source.")
            media_path, imported_subtitles = self._resolve_source(
                source, temporary_directory, forced_language
            )
            metadata = self._probe_media(media_path)
            self._apply_metadata(source, metadata)
            if (
                source.duration_seconds is not None
                and source.duration_seconds > self.settings.max_media_duration_seconds
            ):
                raise ProcessingError(
                    f"Media duration exceeds the configured "
                    f"{self.settings.max_media_duration_seconds}-second limit.",
                    code="media_duration_exceeded",
                )

            segments: list[TranscribedSegment] = []
            if imported_subtitles is None:
                imported_subtitles = self._extract_embedded_subtitles(
                    media_path, temporary_directory
                )
            if imported_subtitles is not None:
                segments = subtitle_segments(
                    imported_subtitles, transcription_language(forced_language)
                )
                source.subtitle_source = source.subtitle_source or "embedded_or_official_subtitles"
                source.transcription_status = "subtitles_imported"

            if not segments:
                self._status(
                    source,
                    MediaProcessingStatus.EXTRACTING_AUDIO,
                    "Extracting a safe mono audio stream.",
                )
                audio_path = self._extract_audio(media_path, temporary_directory)
                self._status(
                    source,
                    MediaProcessingStatus.TRANSCRIBING,
                    f"Transcribing locally with {self.transcription_provider.model_name}.",
                )
                active_job = TranscriptJob(
                    media_source_id=source.id,
                    status=TranscriptJobStatus.RUNNING,
                    model_name=self.transcription_provider.model_name,
                    device=self.settings.transcription_device,
                    compute_type=self.settings.transcription_compute_type,
                    forced_language=transcription_language(
                        forced_language or self.settings.transcription_language
                    ),
                    attempt_number=source.processing_attempts,
                    started_at=datetime.now(UTC),
                )
                self.session.add(active_job)
                self.session.commit()
                result = self.transcription_provider.transcribe(
                    audio_path,
                    language=transcription_language(
                        forced_language or self.settings.transcription_language
                    ),
                )
                segments = result.segments
                source.detected_language = result.language
                source.transcription_status = "complete"
                active_job.detected_language = result.language
                active_job.status = TranscriptJobStatus.COMPLETE
                active_job.completed_at = datetime.now(UTC)
                self.session.add(active_job)
                self.session.commit()

            if not segments:
                raise ProcessingError(
                    "No usable transcript segments were produced.",
                    code="empty_transcript",
                )
            self._persist_segments(source, segments, active_job)
            self._status(
                source,
                MediaProcessingStatus.TRANSCRIPT_READY,
                f"Transcript ready with {len(segments)} timestamped segments.",
            )
            self._index_transcript(source, segments)
            self._status(
                source,
                MediaProcessingStatus.SUMMARISING,
                "Generating transcript intelligence and chapters.",
            )
            resolved_output_language = resolve_output_language(
                output_language,
                " ".join(segment.text for segment in segments),
            )
            self._generate_intelligence(source, segments, resolved_output_language)
            source.ingestion_date = datetime.now(UTC)
            self._status(
                source,
                MediaProcessingStatus.READY,
                "Transcript, vector index, and media intelligence are ready.",
            )
            attempt.completed_at = datetime.now(UTC)
            attempt.final_stage = MediaProcessingStatus.READY.value
            attempt.succeeded = True
            self.session.add(attempt)
            self.session.commit()
            return source
        except ProcessingError as exc:
            if active_job is not None and active_job.status is TranscriptJobStatus.RUNNING:
                active_job.status = TranscriptJobStatus.FAILED
                active_job.error_message = exc.message
                active_job.completed_at = datetime.now(UTC)
                self.session.add(active_job)
            self._fail(source, attempt, exc.code, exc.message, repr(exc), retryable=True)
            return source
        except Exception as exc:
            self._fail(
                source,
                attempt,
                "media_processing_failed",
                "Media processing failed unexpectedly. Inspect the source and retry.",
                repr(exc),
                retryable=True,
            )
            return source
        finally:
            shutil.rmtree(temporary_directory, ignore_errors=True)

    def _resolve_source(
        self,
        source: MediaSource,
        temporary_directory: Path,
        forced_language: str | None,
    ) -> tuple[Path, Path | None]:
        if source.source_kind is MediaSourceKind.UPLOAD:
            if not source.storage_key:
                raise ProcessingError(
                    "The stored media file is missing.", code="stored_media_missing"
                )
            path = self.storage.resolve(source.storage_key)
            if not path.is_file():
                raise ProcessingError(
                    "The stored media file is missing.", code="stored_media_missing"
                )
            return path, None

        if not source.original_url:
            raise ProcessingError("The linked media URL is missing.", code="media_url_missing")
        self._status(
            source,
            MediaProcessingStatus.FETCHING_METADATA,
            "Fetching public metadata without bypassing access controls.",
        )
        if source.source_kind is MediaSourceKind.YOUTUBE:
            return self._download_youtube(source, temporary_directory, forced_language)
        return self._download_public(source, temporary_directory), None

    def _download_public(self, source: MediaSource, temporary_directory: Path) -> Path:
        assert source.original_url is not None
        current_url = validate_public_url(source.original_url)
        destination = temporary_directory / "linked-media"
        total = 0
        digest = hashlib.sha256()
        with httpx.Client(
            timeout=self.settings.media_download_timeout_seconds,
            follow_redirects=False,
        ) as client:
            for _ in range(5):
                with client.stream(
                    "GET",
                    current_url,
                    headers={"User-Agent": "EnterpriseRAG/0.5"},
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ProcessingError(
                                "The media URL returned an invalid redirect.",
                                code="invalid_media_redirect",
                            )
                        current_url = validate_public_url(urljoin(current_url, location))
                        continue
                    if response.status_code >= 400:
                        raise ProcessingError(
                            "The public media URL could not be accessed.",
                            code="public_media_unavailable",
                        )
                    content_type = response.headers.get("content-type", "").split(";")[0]
                    suffix = mimetypes.guess_extension(content_type) or ".bin"
                    destination = destination.with_suffix(suffix)
                    with destination.open("xb") as output:
                        for chunk in response.iter_bytes(1024 * 1024):
                            total += len(chunk)
                            if total > self.settings.max_media_upload_bytes:
                                raise ProcessingError(
                                    "The linked media exceeds the configured download limit.",
                                    code="media_download_too_large",
                                )
                            digest.update(chunk)
                            output.write(chunk)
                    break
            else:
                raise ProcessingError(
                    "The media URL redirected too many times.",
                    code="too_many_media_redirects",
                )
        source.size_bytes = total
        source.checksum_sha256 = digest.hexdigest()
        source.media_type = content_type or "application/octet-stream"
        return destination

    def _download_youtube(
        self,
        source: MediaSource,
        temporary_directory: Path,
        forced_language: str | None,
    ) -> tuple[Path, Path | None]:
        assert source.original_url is not None
        self._status(
            source,
            MediaProcessingStatus.DOWNLOADING_OR_EXTRACTING_SUBTITLES,
            "Looking for official or automatically generated subtitles.",
        )
        metadata = self._run_ytdlp(
            source.original_url,
            {"skip_download": True},
            download=False,
            error_code="youtube_metadata_unavailable",
        )
        source.title = str(metadata.get("title") or source.title)[:500]
        source.author = str(metadata.get("channel") or metadata.get("uploader") or "")[:300] or None
        source.duration_seconds = _float_or_none(metadata.get("duration"))
        source.thumbnail_url = metadata.get("thumbnail")
        source.metadata_json = {
            **source.metadata_json,
            "extractor": metadata.get("extractor"),
            "webpage_url": metadata.get("webpage_url"),
        }
        output_template = temporary_directory / "source.%(ext)s"
        requested_language = transcription_language(
            forced_language or self.settings.transcription_language
        )
        subtitle_languages = [f"{requested_language}.*"] if requested_language else ["ar.*", "en.*"]
        try:
            self._run_ytdlp(
                source.original_url,
                {
                    "skip_download": True,
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitlesformat": "vtt",
                    "subtitleslangs": subtitle_languages,
                    "outtmpl": str(output_template),
                },
                download=False,
                error_code="youtube_subtitles_unavailable",
            )
        except ProcessingError as exc:
            if exc.code == "youtube_authentication_required":
                raise
        subtitle_files = sorted(
            temporary_directory.glob("source*.vtt"),
            key=lambda path: (
                0 if requested_language and f".{requested_language}" in path.name else 1,
                path.name,
            ),
        )
        if subtitle_files:
            source.subtitle_source = "official_or_auto_subtitles"
            placeholder = temporary_directory / "metadata-only"
            placeholder.touch()
            return placeholder, subtitle_files[0]

        self._run_ytdlp(
            source.original_url,
            {
                "format": "bestaudio/best",
                "max_filesize": self.settings.max_media_upload_bytes,
                "outtmpl": str(output_template),
            },
            download=True,
            error_code="youtube_media_unavailable",
        )
        downloaded = [
            path
            for path in temporary_directory.glob("source.*")
            if path.suffix.lower() not in {".vtt", ".json", ".part"}
        ]
        if not downloaded:
            raise ProcessingError(
                "Public media could not be retrieved. The source may restrict downloads.",
                code="youtube_media_unavailable",
            )
        return downloaded[0], None

    def _probe_media(self, media_path: Path) -> dict[str, object]:
        if media_path.name == "metadata-only":
            return {"format": {"duration": None}, "streams": []}
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,format_name:stream=codec_type,codec_name",
            "-of",
            "json",
            str(media_path),
        ]
        metadata = self._run_json_command(command, "invalid_or_corrupt_media")
        streams = metadata.get("streams", [])
        if not any(
            stream.get("codec_type") in {"audio", "video"}
            for stream in streams
            if isinstance(stream, dict)
        ):
            raise ProcessingError(
                "The file does not contain a readable audio or video stream.",
                code="media_stream_missing",
            )
        return metadata

    def _apply_metadata(self, source: MediaSource, metadata: dict[str, object]) -> None:
        format_data = metadata.get("format", {})
        if isinstance(format_data, dict):
            source.duration_seconds = source.duration_seconds or _float_or_none(
                format_data.get("duration")
            )
            source.metadata_json = {
                **source.metadata_json,
                "format_name": format_data.get("format_name"),
                "streams": metadata.get("streams", []),
            }
        self.session.add(source)
        self.session.commit()

    def _extract_embedded_subtitles(
        self, media_path: Path, temporary_directory: Path
    ) -> Path | None:
        if media_path.name == "metadata-only":
            return None
        destination = temporary_directory / "embedded.vtt"
        command = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(media_path),
            "-map",
            "0:s:0",
            "-c:s",
            "webvtt",
            "-y",
            str(destination),
        ]
        self._run_command(command, allow_failure=True)
        return destination if destination.is_file() and destination.stat().st_size else None

    def _extract_audio(self, media_path: Path, temporary_directory: Path) -> Path:
        destination = temporary_directory / "audio.wav"
        command = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-y",
            str(destination),
        ]
        self._run_command(command, error_code="audio_extraction_failed")
        if not destination.is_file() or destination.stat().st_size <= 44:
            raise ProcessingError(
                "No usable audio stream could be extracted.",
                code="audio_stream_missing",
            )
        return destination

    def _persist_segments(
        self,
        source: MediaSource,
        values: list[TranscribedSegment],
        job: TranscriptJob | None,
    ) -> None:
        segments = [
            TranscriptSegment(
                id=stable_segment_id(source.id, index, value.text),
                media_source_id=source.id,
                transcript_job_id=job.id if job is not None else None,
                segment_index=index,
                start_time=value.start,
                end_time=value.end,
                text=value.text,
                detected_language=value.language,
                confidence=value.confidence,
            )
            for index, value in enumerate(values)
        ]
        self.media.replace_segments(source.id, segments)
        if source.detected_language is None:
            source.detected_language = next(
                (value.language for value in values if value.language), None
            )
        self.session.add(source)
        self.session.commit()

    def _index_transcript(self, source: MediaSource, segments: list[TranscribedSegment]) -> None:
        self._status(
            source,
            MediaProcessingStatus.CHUNKING,
            "Creating timestamp-aware transcript chunks.",
        )
        full_text = "\n".join(value.text for value in segments)
        checksum = hashlib.sha256(f"media-transcript:{source.id}:{full_text}".encode()).hexdigest()
        relative_key = Path(source.knowledge_base_id) / "transcripts" / f"{source.id}.txt"
        transcript_path = self.storage.root / relative_key
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(full_text, encoding="utf-8")

        document = (
            self.documents.get(source.transcript_document_id)
            if source.transcript_document_id
            else None
        )
        if document is None:
            document = Document(
                knowledge_base_id=source.knowledge_base_id,
                name=f"{source.title} — transcript.txt",
                document_type=DocumentType.TXT,
                media_type="text/plain",
                size_bytes=transcript_path.stat().st_size,
                checksum_sha256=checksum,
                storage_key=relative_key.as_posix(),
                status=DocumentStatus.CHUNKING,
                status_message="Building timestamp-aware transcript chunks.",
            )
            self.session.add(document)
            self.session.flush()
            source.transcript_document_id = document.id
        else:
            self.documents.delete_generated_content(document.id)
            document.name = f"{source.title} — transcript.txt"
            document.size_bytes = transcript_path.stat().st_size
            document.checksum_sha256 = checksum
            document.status = DocumentStatus.CHUNKING

        extracted_sections: list[ExtractedSection] = []
        cursor = 0
        for index, segment in enumerate(segments):
            extracted_sections.append(
                ExtractedSection(
                    section_index=index,
                    text=segment.text,
                    page_number=None,
                    heading=f"{_format_timestamp(segment.start)}",
                    start_char=cursor,
                    end_char=cursor + len(segment.text),
                    metadata={
                        "media_source_id": source.id,
                        "timestamp_start": segment.start,
                        "timestamp_end": segment.end,
                        "segment_index": index,
                    },
                )
            )
            cursor += len(segment.text) + 1
        sections = [
            DocumentSection(
                id=hashlib.sha256(f"{document.id}:media-section:{index}".encode()).hexdigest(),
                document_id=document.id,
                section_index=index,
                page_number=None,
                heading=value.heading,
                text=value.text,
                start_char=value.start_char,
                end_char=value.end_char,
                metadata_json=value.metadata,
            )
            for index, value in enumerate(extracted_sections)
        ]
        self.session.add_all(sections)
        chunk_values = TextChunker(self.settings.chunk_size, self.settings.chunk_overlap).chunk(
            document_id=document.id,
            knowledge_base_id=source.knowledge_base_id,
            sections=self._group_segments(source.id, segments),
        )
        chunks = [
            DocumentChunk(
                id=value.id,
                document_id=document.id,
                knowledge_base_id=source.knowledge_base_id,
                chunk_index=value.chunk_index,
                text=value.text,
                page_number=None,
                section_index=value.section_index,
                start_char=value.start_char,
                end_char=value.end_char,
                character_count=value.character_count,
                token_estimate=value.token_estimate,
                extraction_metadata=value.metadata,
            )
            for value in chunk_values
        ]
        self.session.add_all(chunks)
        document.extracted_text = full_text
        document.character_count = len(full_text)
        document.chunk_count = len(chunks)
        document.page_count = None
        document.extraction_metadata = {
            "source": "media_transcript",
            "media_source_id": source.id,
            "segment_count": len(segments),
        }
        self.session.commit()

        self._status(
            source,
            MediaProcessingStatus.EMBEDDING,
            f"Embedding transcript with {self.embedding_provider.model_name}.",
        )
        embeddings = self.embedding_provider.embed_documents([chunk.text for chunk in chunks])
        self._status(
            source,
            MediaProcessingStatus.INDEXING,
            "Indexing timestamp-aware transcript vectors.",
        )
        count = self.vector_store.upsert(
            chunks, embeddings, model_name=self.embedding_provider.model_name
        )
        document.indexed_chunk_count = count
        document.embedding_model = self.embedding_provider.model_name
        document.status = DocumentStatus.READY_FOR_CHAT
        document.status_message = "Transcript indexed and ready for questions."
        document.indexing_completed_at = datetime.now(UTC)
        source.transcript_document_id = document.id
        self.session.add_all([document, source])
        self.session.commit()

    def _group_segments(
        self, media_source_id: str, segments: list[TranscribedSegment]
    ) -> list[ExtractedSection]:
        groups: list[list[TranscribedSegment]] = []
        current: list[TranscribedSegment] = []
        size = 0
        for segment in segments:
            if current and size + len(segment.text) > self.settings.chunk_size:
                groups.append(current)
                current = []
                size = 0
            current.append(segment)
            size += len(segment.text) + 1
        if current:
            groups.append(current)
        result: list[ExtractedSection] = []
        cursor = 0
        for index, group in enumerate(groups):
            text = " ".join(value.text for value in group)
            result.append(
                ExtractedSection(
                    section_index=index,
                    text=text,
                    page_number=None,
                    heading=f"Transcript {_format_timestamp(group[0].start)}",
                    start_char=cursor,
                    end_char=cursor + len(text),
                    metadata={
                        "media_source_id": media_source_id,
                        "timestamp_start": group[0].start,
                        "timestamp_end": group[-1].end,
                        "segment_start": group[0].index,
                        "segment_end": group[-1].index,
                        "timestamped_segments": [
                            {
                                "start": value.start,
                                "end": value.end,
                                "text": value.text,
                            }
                            for value in group
                        ],
                    },
                )
            )
            cursor += len(text) + 1
        return result

    def _generate_intelligence(
        self,
        source: MediaSource,
        segments: list[TranscribedSegment],
        output_language: str,
    ) -> None:
        structured = self.intelligence.analyze(segments, output_language)
        chapters = [
            MediaChapter(
                id=hashlib.sha256(f"{source.id}:chapter:{value.index}".encode()).hexdigest(),
                media_source_id=source.id,
                chapter_index=value.index,
                start_time=value.start,
                end_time=value.end,
                title=value.title,
                summary=value.summary,
            )
            for value in structured.pop("chapters")
        ]
        self.media.replace_chapters(source.id, chapters)
        self.media.upsert_summary(
            MediaSummary(
                media_source_id=source.id,
                summary_kind="intelligence",
                content=str(structured["detailed_summary"]),
                structured_data=structured,
                model_name=self.intelligence.model_name,
            )
        )
        self.session.commit()

    def _readable_cookie_file(self) -> Path | None:
        configured = self.settings.ytdlp_cookies_file
        if configured is None:
            return None
        try:
            path = configured.expanduser()
            if path.is_file() and os.access(path, os.R_OK):
                return path
        except OSError:
            return None
        return None

    def _run_ytdlp(
        self,
        url: str,
        options: dict[str, object],
        *,
        download: bool,
        error_code: str,
    ) -> dict[str, object]:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise ProcessingError(
                "YouTube support is unavailable in this deployment. "
                "Upload the media file directly.",
                code="youtube_tool_unavailable",
            ) from exc

        safe_options: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "noprogress": True,
            "socket_timeout": self.settings.media_download_timeout_seconds,
            "logger": _SilentYtdlpLogger(),
            **options,
        }
        cookie_file = self._readable_cookie_file()
        if cookie_file is not None:
            safe_options["cookiefile"] = str(cookie_file)
        try:
            with YoutubeDL(safe_options) as downloader:
                value = downloader.extract_info(url, download=download)
        except Exception as exc:
            detail = str(exc).lower()
            if any(pattern in detail for pattern in YOUTUBE_AUTH_PATTERNS):
                raise ProcessingError(
                    YOUTUBE_COOKIE_REQUIRED_MESSAGE,
                    code="youtube_authentication_required",
                ) from None
            raise ProcessingError(
                "YouTube could not provide this media. Update the server cookies, retry later, "
                "or upload the media file directly.",
                code=error_code,
            ) from None
        if not isinstance(value, dict):
            raise ProcessingError(
                "YouTube returned invalid media metadata. Upload the media file directly.",
                code=error_code,
            )
        return value

    def _status(self, source: MediaSource, status: MediaProcessingStatus, message: str) -> None:
        source.status = status
        source.progress_stage = STAGE_NUMBER[status]
        source.status_message = message
        self.session.add(source)
        self.session.commit()

    def _fail(
        self,
        source: MediaSource,
        attempt: MediaProcessingAttempt,
        code: str,
        safe_message: str,
        technical_message: str,
        *,
        retryable: bool,
    ) -> None:
        self.session.rollback()
        current = self.media.get(source.id)
        if current is None:
            return
        failed_during_transcription = current.status is MediaProcessingStatus.TRANSCRIBING
        current.status = MediaProcessingStatus.FAILED
        current.status_message = safe_message
        current.error_code = code
        current.safe_error_message = safe_message
        current.technical_error_message = technical_message[:4000]
        current.retryable = retryable
        current.failed_at = datetime.now(UTC)
        if failed_during_transcription:
            current.transcription_status = "failed"
        stored_attempt = self.session.get(MediaProcessingAttempt, attempt.id)
        if stored_attempt is not None:
            stored_attempt.completed_at = datetime.now(UTC)
            stored_attempt.final_stage = source.status.value
            stored_attempt.succeeded = False
            stored_attempt.error_code = code
            self.session.add(stored_attempt)
        self.session.add(current)
        self.session.commit()

    def _run_json_command(self, command: list[str], error_code: str) -> dict[str, object]:
        completed = self._run_command(command, error_code=error_code)
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProcessingError("Media metadata could not be read.", code=error_code) from exc
        if not isinstance(value, dict):
            raise ProcessingError("Media metadata was invalid.", code=error_code)
        return value

    def _run_command(
        self,
        command: list[str],
        *,
        error_code: str = "media_command_failed",
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.settings.media_processing_timeout_seconds,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            if allow_failure:
                return subprocess.CompletedProcess(command, 1, "", repr(exc))
            raise ProcessingError(
                "A required local media tool failed or timed out.",
                code=error_code,
            ) from exc
        if completed.returncode != 0 and not allow_failure:
            safe_detail = re.sub(r"https?://\S+", "[redacted-url]", completed.stderr)
            raise ProcessingError(
                f"The media source could not be processed: {safe_detail[-300:]}",
                code=error_code,
            )
        return completed


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _format_timestamp(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d}"
