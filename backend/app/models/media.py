import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, DemoLifecycleMixin, TimestampMixin


class MediaSourceKind(StrEnum):
    UPLOAD = "upload"
    PUBLIC_URL = "public_url"
    YOUTUBE = "youtube"


class MediaProcessingStatus(StrEnum):
    UPLOADED_OR_LINKED = "uploaded_or_linked"
    VALIDATING = "validating"
    FETCHING_METADATA = "fetching_metadata"
    DOWNLOADING_OR_EXTRACTING_SUBTITLES = "downloading_or_extracting_subtitles"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    TRANSCRIPT_READY = "transcript_ready"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    SUMMARISING = "summarising"
    READY = "ready"
    FAILED = "failed"


class TranscriptJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class MediaSource(DemoLifecycleMixin, TimestampMixin, Base):
    __tablename__ = "media_sources"
    __table_args__ = (
        Index("ix_media_sources_kb_status", "knowledge_base_id", "status"),
        UniqueConstraint(
            "knowledge_base_id",
            "checksum_sha256",
            name="uq_media_sources_kb_checksum",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transcript_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    source_kind: Mapped[MediaSourceKind] = mapped_column(
        SqlEnum(MediaSourceKind, native_enum=False, length=24), nullable=False
    )
    original_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_platform: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtitle_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transcription_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    status: Mapped[MediaProcessingStatus] = mapped_column(
        SqlEnum(MediaProcessingStatus, native_enum=False, length=48),
        default=MediaProcessingStatus.UPLOADED_OR_LINKED,
        nullable=False,
    )
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    progress_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ingestion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transcript_jobs: Mapped[list["TranscriptJob"]] = relationship(
        back_populates="media_source", cascade="all, delete-orphan"
    )
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="media_source",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.segment_index",
    )
    summaries: Mapped[list["MediaSummary"]] = relationship(
        back_populates="media_source", cascade="all, delete-orphan"
    )
    chapters: Mapped[list["MediaChapter"]] = relationship(
        back_populates="media_source",
        cascade="all, delete-orphan",
        order_by="MediaChapter.chapter_index",
    )
    attempts: Mapped[list["MediaProcessingAttempt"]] = relationship(
        back_populates="media_source", cascade="all, delete-orphan"
    )
    exports: Mapped[list["MediaExportRecord"]] = relationship(
        back_populates="media_source", cascade="all, delete-orphan"
    )


class TranscriptJob(TimestampMixin, Base):
    __tablename__ = "transcript_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    media_source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[TranscriptJobStatus] = mapped_column(
        SqlEnum(TranscriptJobStatus, native_enum=False, length=20), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    device: Mapped[str] = mapped_column(String(30), nullable=False)
    compute_type: Mapped[str] = mapped_column(String(30), nullable=False)
    forced_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    media_source: Mapped[MediaSource] = relationship(back_populates="transcript_jobs")


class TranscriptSegment(TimestampMixin, Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint("media_source_id", "segment_index", name="uq_transcript_segment_index"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    media_source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transcript_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("transcript_jobs.id", ondelete="SET NULL"), nullable=True
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    media_source: Mapped[MediaSource] = relationship(back_populates="transcript_segments")


class MediaSummary(TimestampMixin, Base):
    __tablename__ = "media_summaries"
    __table_args__ = (
        UniqueConstraint("media_source_id", "summary_kind", name="uq_media_summary_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    media_source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)

    media_source: Mapped[MediaSource] = relationship(back_populates="summaries")


class MediaChapter(TimestampMixin, Base):
    __tablename__ = "media_chapters"
    __table_args__ = (
        UniqueConstraint("media_source_id", "chapter_index", name="uq_media_chapter_index"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    media_source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    media_source: Mapped[MediaSource] = relationship(back_populates="chapters")


class MediaProcessingAttempt(TimestampMixin, Base):
    __tablename__ = "media_processing_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    media_source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_stage: Mapped[str | None] = mapped_column(String(60), nullable=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    media_source: Mapped[MediaSource] = relationship(back_populates="attempts")


class MediaExportRecord(TimestampMixin, Base):
    __tablename__ = "media_export_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    media_source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    export_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)

    media_source: Mapped[MediaSource] = relationship(back_populates="exports")
