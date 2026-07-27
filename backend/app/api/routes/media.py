from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.ai.generation_queue import GenerationQueue
from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.api.dependencies import (
    get_db_session,
    get_embedding_provider,
    get_file_storage,
    get_generation_provider,
    get_generation_queue,
    get_runtime_settings,
)
from app.core.config import Settings
from app.core.errors import (
    ConflictError,
    GenerationQueueFullError,
    GenerationTimeoutError,
    NotFoundError,
)
from app.db.session import session_scope
from app.models.media import MediaProcessingStatus, MediaSource
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.repositories.media import MediaRepository
from app.schemas.media import (
    ActionItem,
    ChapterRead,
    MediaDetailRead,
    MediaProcessingAttemptRead,
    MediaSourceList,
    MediaSourceRead,
    MediaUrlCreate,
    MentionedEntity,
    TranscriptJobRead,
    TranscriptRead,
    TranscriptSearchResponse,
    TranscriptSearchResult,
    TranscriptSegmentRead,
    VideoIntelligenceRead,
)
from app.schemas.rag import RagAnswerRead, RagAskRequest
from app.services.media import MediaIngestionService, MediaProcessingService
from app.services.rag import RagService
from app.services.storage import LocalFileStorage

router = APIRouter(tags=["media"])

ACTIVE_MEDIA_STATUSES = {
    MediaProcessingStatus.VALIDATING,
    MediaProcessingStatus.FETCHING_METADATA,
    MediaProcessingStatus.DOWNLOADING_OR_EXTRACTING_SUBTITLES,
    MediaProcessingStatus.EXTRACTING_AUDIO,
    MediaProcessingStatus.TRANSCRIBING,
    MediaProcessingStatus.TRANSCRIPT_READY,
    MediaProcessingStatus.CHUNKING,
    MediaProcessingStatus.EMBEDDING,
    MediaProcessingStatus.INDEXING,
    MediaProcessingStatus.SUMMARISING,
}


def _mark_media_busy(request: Request, media_source_id: str, code: str, message: str) -> None:
    with session_scope(request.app.state.session_factory) as session:
        source = MediaRepository(session).get(media_source_id)
        if source is None:
            return
        source.status = MediaProcessingStatus.FAILED
        source.status_message = message
        source.safe_error_message = message
        source.error_code = code
        source.retryable = True
        session.add(source)
        session.commit()


async def run_media_processing(
    request: Request,
    media_source_id: str,
    forced_language: str | None,
    output_language: str = "auto",
) -> None:
    queue = request.app.state.generation_queue
    settings = request.app.state.settings
    try:
        slot = await queue.acquire(timeout=settings.generation_queue_timeout_seconds)
    except (TimeoutError, GenerationQueueFullError):
        _mark_media_busy(
            request,
            media_source_id,
            "server_busy",
            "The server is busy with another AI task. Retry this media job shortly.",
        )
        return

    def process() -> None:
        with session_scope(request.app.state.session_factory) as session:
            MediaProcessingService(
                session=session,
                storage=request.app.state.file_storage,
                settings=settings,
                embedding_provider=request.app.state.embedding_provider,
                transcription_provider=request.app.state.transcription_provider,
            ).process(
                media_source_id,
                forced_language=forced_language,
                output_language=output_language,
            )

    try:
        await queue.execute(slot, process, timeout=settings.media_processing_timeout_seconds)
    except TimeoutError:
        _mark_media_busy(
            request,
            media_source_id,
            "media_processing_timeout",
            "Media processing exceeded the safe time limit. Try a shorter file.",
        )


@router.post(
    "/knowledge-bases/{knowledge_base_id}/media",
    response_model=MediaSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    knowledge_base_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    auto_process: Annotated[bool, Form()] = True,
    forced_language: Annotated[Literal["auto", "ar", "en"], Form()] = "auto",
    output_language: Annotated[Literal["auto", "ar", "en"], Form()] = "auto",
) -> MediaSourceRead:
    source = await MediaIngestionService(
        session=session, storage=storage, settings=settings
    ).upload(knowledge_base_id, file)
    if auto_process:
        background_tasks.add_task(
            run_media_processing, request, source.id, forced_language, output_language
        )
    return MediaSourceRead.model_validate(source)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/media/from-url",
    response_model=MediaSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def link_media(
    knowledge_base_id: str,
    payload: MediaUrlCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> MediaSourceRead:
    source = MediaIngestionService(session=session, storage=storage, settings=settings).create_url(
        knowledge_base_id, str(payload.url), payload.title
    )
    if payload.auto_process:
        background_tasks.add_task(
            run_media_processing,
            request,
            source.id,
            payload.forced_language,
            payload.output_language,
        )
    return MediaSourceRead.model_validate(source)


@router.get(
    "/knowledge-bases/{knowledge_base_id}/media",
    response_model=MediaSourceList,
)
def list_media(
    knowledge_base_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> MediaSourceList:
    if KnowledgeBaseRepository(session).get(knowledge_base_id) is None:
        raise NotFoundError("Knowledge base")
    values = MediaRepository(session).list_for_knowledge_base(knowledge_base_id)
    return MediaSourceList(
        items=[MediaSourceRead.model_validate(value) for value in values],
        total=len(values),
    )


@router.get("/media/{media_source_id}", response_model=MediaDetailRead)
def media_details(
    media_source_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> MediaDetailRead:
    source = _get_source(session, media_source_id)
    base = MediaSourceRead.model_validate(source).model_dump()
    return MediaDetailRead(
        **base,
        transcript_jobs=[
            TranscriptJobRead.model_validate(value) for value in source.transcript_jobs
        ],
        attempt_history=[
            MediaProcessingAttemptRead.model_validate(value) for value in source.attempts
        ],
        segment_count=len(source.transcript_segments),
        chapter_count=len(source.chapters),
        has_summary=bool(source.summaries),
    )


@router.get("/media/{media_source_id}/content", response_class=FileResponse)
def media_content(
    media_source_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
) -> FileResponse:
    source = _get_source(session, media_source_id)
    if not source.storage_key:
        raise NotFoundError("Stored media")
    path = storage.resolve(source.storage_key)
    if not path.is_file():
        raise NotFoundError("Stored media")
    return FileResponse(
        path,
        media_type=source.media_type,
        filename=source.original_filename or source.title,
        content_disposition_type="inline",
    )


def _queue_media(
    *,
    source: MediaSource,
    session: Session,
    request: Request,
    background_tasks: BackgroundTasks,
    forced_language: str | None,
    output_language: str,
    retry_only: bool,
) -> MediaSourceRead:
    if source.status in ACTIVE_MEDIA_STATUSES:
        raise ConflictError(
            code="media_processing_active",
            message="Media processing is already active.",
        )
    if retry_only and source.status is not MediaProcessingStatus.FAILED:
        raise ConflictError(
            code="media_not_failed",
            message="Only failed media can use the retry endpoint.",
        )
    source.status = MediaProcessingStatus.VALIDATING
    source.status_message = "Media processing has been queued."
    source.safe_error_message = None
    source.error_code = None
    session.add(source)
    session.commit()
    session.refresh(source)
    result = MediaSourceRead.model_validate(source)
    background_tasks.add_task(
        run_media_processing, request, source.id, forced_language, output_language
    )
    return result


@router.post(
    "/media/{media_source_id}/process",
    response_model=MediaSourceRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_media(
    media_source_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db_session)],
    forced_language: Annotated[Literal["auto", "ar", "en"], Query()] = "auto",
    output_language: Annotated[Literal["auto", "ar", "en"], Query()] = "auto",
) -> MediaSourceRead:
    return _queue_media(
        source=_get_source(session, media_source_id),
        session=session,
        request=request,
        background_tasks=background_tasks,
        forced_language=forced_language,
        output_language=output_language,
        retry_only=False,
    )


@router.post(
    "/media/{media_source_id}/retry",
    response_model=MediaSourceRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_media(
    media_source_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db_session)],
    forced_language: Annotated[Literal["auto", "ar", "en"], Query()] = "auto",
    output_language: Annotated[Literal["auto", "ar", "en"], Query()] = "auto",
) -> MediaSourceRead:
    return _queue_media(
        source=_get_source(session, media_source_id),
        session=session,
        request=request,
        background_tasks=background_tasks,
        forced_language=forced_language,
        output_language=output_language,
        retry_only=True,
    )


@router.get("/media/{media_source_id}/transcript", response_model=TranscriptRead)
def get_transcript(
    media_source_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    include_full_text: Annotated[bool, Query()] = True,
) -> TranscriptRead:
    source = _get_source(session, media_source_id)
    repository = MediaRepository(session)
    all_segments = repository.all_segments(media_source_id)
    values = all_segments[offset : offset + limit]
    return TranscriptRead(
        media_source_id=source.id,
        title=source.title,
        language=source.detected_language,
        duration_seconds=source.duration_seconds,
        full_text=" ".join(value.text for value in (all_segments if include_full_text else values)),
        segments=[TranscriptSegmentRead.model_validate(value) for value in values],
        total_segments=len(all_segments),
        offset=offset,
        limit=limit,
    )


@router.get(
    "/media/{media_source_id}/transcript/search",
    response_model=TranscriptSearchResponse,
)
def search_transcript(
    media_source_id: str,
    query: Annotated[str, Query(min_length=2, max_length=300)],
    session: Annotated[Session, Depends(get_db_session)],
) -> TranscriptSearchResponse:
    _get_source(session, media_source_id)
    terms = {term.lower() for term in query.split() if len(term) > 1}
    results: list[TranscriptSearchResult] = []
    for segment in MediaRepository(session).all_segments(media_source_id):
        lower = segment.text.lower()
        matched = sorted(term for term in terms if term in lower)
        if matched:
            results.append(
                TranscriptSearchResult(
                    segment=TranscriptSegmentRead.model_validate(segment),
                    matched_terms=matched,
                )
            )
    return TranscriptSearchResponse(query=query, results=results, total=len(results))


@router.get(
    "/media/{media_source_id}/intelligence",
    response_model=VideoIntelligenceRead,
)
def media_intelligence(
    media_source_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> VideoIntelligenceRead:
    source = _get_source(session, media_source_id)
    summary = MediaRepository(session).summary(media_source_id)
    if summary is None:
        raise ConflictError(
            code="media_intelligence_not_ready",
            message="Media intelligence is not ready yet.",
        )
    values = summary.structured_data
    return VideoIntelligenceRead(
        media_source_id=source.id,
        short_summary=str(values.get("short_summary", "")),
        detailed_summary=str(values.get("detailed_summary", summary.content)),
        key_points=list(values.get("key_points", [])),
        chapters=[ChapterRead.model_validate(value) for value in source.chapters],
        action_items=[ActionItem.model_validate(value) for value in values.get("action_items", [])],
        decisions=list(values.get("decisions", [])),
        entities=[MentionedEntity.model_validate(value) for value in values.get("entities", [])],
        important_quotes=list(values.get("important_quotes", [])),
        lecture_outline=list(values.get("lecture_outline", [])),
        explained_concepts=list(values.get("explained_concepts", [])),
        definitions=dict(values.get("definitions", {})),
        examples=list(values.get("examples", [])),
        quiz_questions=list(values.get("quiz_questions", [])),
        revision_notes=list(values.get("revision_notes", [])),
        glossary=dict(values.get("glossary", {})),
        important_timestamps=list(values.get("important_timestamps", [])),
        meeting_summary=str(values.get("meeting_summary", "")),
        unresolved_issues=list(values.get("unresolved_issues", [])),
        language=source.detected_language,
        output_language="ar" if values.get("output_language") == "ar" else "en",
        generated_at=summary.updated_at,
        model_name=summary.model_name,
    )


@router.post("/media/{media_source_id}/ask", response_model=RagAnswerRead)
async def ask_media(
    media_source_id: str,
    payload: RagAskRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
    generation_queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> RagAnswerRead:
    source = _get_source(session, media_source_id)
    if not source.transcript_document_id:
        raise ConflictError(
            code="transcript_not_indexed",
            message="The transcript is not indexed yet.",
        )
    scoped = payload.model_copy(update={"source_document_ids": [source.transcript_document_id]})
    try:
        slot = await generation_queue.acquire(timeout=settings.generation_queue_timeout_seconds)
    except TimeoutError as exc:
        raise GenerationQueueFullError(
            "The server is busy with another model request. Please retry shortly."
        ) from exc
    try:
        return await generation_queue.execute(
            slot,
            lambda: RagService(
                session=session,
                settings=settings,
                embedding_provider=embedding_provider,
                generation_provider=generation_provider,
            ).ask(source.knowledge_base_id, scoped),
            timeout=settings.generation_timeout_seconds,
        )
    except TimeoutError as exc:
        raise GenerationTimeoutError(
            "The media answer could not be generated in time. Please retry."
        ) from exc


@router.get("/media/{media_source_id}/export/{export_kind}")
def export_media(
    media_source_id: str,
    export_kind: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    source = _get_source(session, media_source_id)
    repository = MediaRepository(session)
    segments = repository.all_segments(media_source_id)
    if export_kind == "transcript.txt":
        content = "\n".join(value.text for value in segments)
        media_type = "text/plain"
    elif export_kind == "transcript.md":
        content = "\n\n".join(
            f"**{_format_timestamp(value.start_time)}** {value.text}" for value in segments
        )
        media_type = "text/markdown"
    elif export_kind == "transcript.json":
        content = json.dumps(
            [
                {
                    "id": value.id,
                    "start": value.start_time,
                    "end": value.end_time,
                    "text": value.text,
                    "language": value.detected_language,
                    "confidence": value.confidence,
                }
                for value in segments
            ],
            ensure_ascii=False,
            indent=2,
        )
        media_type = "application/json"
    elif export_kind == "summary.md":
        summary = repository.summary(media_source_id)
        if summary is None:
            raise ConflictError(
                code="media_intelligence_not_ready",
                message="Media intelligence is not ready yet.",
            )
        content = f"# {source.title}\n\n{summary.content}\n"
        media_type = "text/markdown"
    else:
        raise NotFoundError("Export format")
    kind, format_name = export_kind.split(".", 1)
    repository.record_export(media_source_id, kind, format_name)
    safe_filename = "".join(
        character if character.isalnum() or character in "-_" else "-" for character in source.title
    )[:80]
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}-{export_kind}"'},
    )


@router.delete("/media/{media_source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    media_source_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> None:
    MediaIngestionService(session=session, storage=storage, settings=settings).delete(
        media_source_id
    )


def _get_source(session: Session, media_source_id: str) -> MediaSource:
    source = MediaRepository(session).get(media_source_id)
    if source is None:
        raise NotFoundError("Media source")
    return source


def _format_timestamp(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d}"
