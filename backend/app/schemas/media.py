from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.media import MediaProcessingStatus, MediaSourceKind, TranscriptJobStatus


class MediaUrlCreate(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=500)
    forced_language: Literal["auto", "ar", "en"] = "auto"
    output_language: Literal["auto", "ar", "en"] = "auto"
    auto_process: bool = True


class MediaSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    knowledge_base_id: str
    transcript_document_id: str | None
    source_kind: MediaSourceKind
    original_url: str | None
    original_filename: str | None
    media_type: str | None
    size_bytes: int | None
    source_platform: str | None
    title: str
    author: str | None
    duration_seconds: float | None
    detected_language: str | None
    thumbnail_url: str | None
    subtitle_source: str | None
    transcription_status: str
    status: MediaProcessingStatus
    status_message: str | None
    progress_stage: int
    warnings: list[str]
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    error_code: str | None
    safe_error_message: str | None
    retryable: bool
    processing_attempts: int
    ingestion_date: datetime | None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime
    expires_at: datetime | None
    is_protected: bool


class MediaSourceList(BaseModel):
    items: list[MediaSourceRead]
    total: int


class TranscriptJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: TranscriptJobStatus
    model_name: str
    device: str
    compute_type: str
    forced_language: str | None
    detected_language: str | None
    attempt_number: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class TranscriptSegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    segment_index: int
    start_time: float
    end_time: float
    text: str
    detected_language: str | None
    confidence: float | None


class TranscriptRead(BaseModel):
    media_source_id: str
    title: str
    language: str | None
    duration_seconds: float | None
    full_text: str
    segments: list[TranscriptSegmentRead]
    total_segments: int
    offset: int
    limit: int


class TranscriptSearchResult(BaseModel):
    segment: TranscriptSegmentRead
    matched_terms: list[str]


class TranscriptSearchResponse(BaseModel):
    query: str
    results: list[TranscriptSearchResult]
    total: int


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chapter_index: int
    start_time: float
    end_time: float
    title: str
    summary: str


class MentionedEntity(BaseModel):
    name: str
    category: str
    mentions: int


class ActionItem(BaseModel):
    text: str
    owner: str | None = None
    deadline: str | None = None
    timestamp: float | None = None


class VideoIntelligenceRead(BaseModel):
    media_source_id: str
    short_summary: str
    detailed_summary: str
    key_points: list[str]
    chapters: list[ChapterRead]
    action_items: list[ActionItem]
    decisions: list[str]
    entities: list[MentionedEntity]
    important_quotes: list[str]
    lecture_outline: list[str]
    explained_concepts: list[str]
    definitions: dict[str, str]
    examples: list[str]
    quiz_questions: list[str]
    revision_notes: list[str]
    glossary: dict[str, str]
    important_timestamps: list[float]
    meeting_summary: str
    unresolved_issues: list[str]
    language: str | None
    output_language: Literal["ar", "en"]
    generated_at: datetime
    model_name: str


class MediaProcessingAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempt_number: int
    started_at: datetime
    completed_at: datetime | None
    final_stage: str | None
    succeeded: bool
    error_code: str | None


class MediaDetailRead(MediaSourceRead):
    transcript_jobs: list[TranscriptJobRead]
    attempt_history: list[MediaProcessingAttemptRead]
    segment_count: int
    chapter_count: int
    has_summary: bool
