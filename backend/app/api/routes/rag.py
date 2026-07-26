import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.generation_queue import GenerationQueue
from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.ai.langchain_engine.service import LangChainRagService
from app.api.dependencies import (
    get_db_session,
    get_embedding_provider,
    get_generation_provider,
    get_generation_queue,
    get_runtime_settings,
)
from app.core.config import Settings
from app.core.errors import GenerationQueueFullError, GenerationTimeoutError, NotFoundError
from app.models.document import DocumentChunk
from app.repositories.conversations import ConversationRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.conversation import (
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionList,
    ChatSessionRead,
)
from app.schemas.rag import (
    RagAnswerRead,
    RagAskRequest,
    RagConfigurationRead,
    RetrievalRequest,
    RetrievalResponse,
)
from app.services.rag import RagService, source_to_read
from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


def _model_is_cached(settings: Settings, model_name: str) -> bool:
    snapshots = settings.model_cache_path / f"models--{model_name.replace('/', '--')}" / "snapshots"
    return snapshots.is_dir() and any(value.is_dir() for value in snapshots.iterdir())


@router.post(
    "/knowledge-bases/{knowledge_base_id}/ask",
    response_model=RagAnswerRead,
)
async def ask_knowledge_base(
    knowledge_base_id: str,
    payload: RagAskRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
    generation_queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> RagAnswerRead:
    try:
        slot = await generation_queue.acquire(
            timeout=settings.generation_queue_timeout_seconds,
        )
    except TimeoutError as exc:
        raise GenerationQueueFullError(
            "The server is busy with another model request. Please retry shortly."
        ) from exc
    try:
        return await generation_queue.execute(
            slot,
            lambda: _run_ask(
                knowledge_base_id,
                payload,
                request,
                session,
                settings,
                embedding_provider,
                generation_provider,
            ),
            timeout=settings.generation_timeout_seconds,
        )
    except TimeoutError as exc:
        raise GenerationTimeoutError(
            "The answer could not be generated in time. "
            "The model may be busy — please retry."
        ) from exc


def _run_ask(
    knowledge_base_id: str,
    payload: RagAskRequest,
    request: Request,
    session: Session,
    settings: Settings,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
) -> RagAnswerRead:
    if settings.rag_engine == "langchain":
        return LangChainRagService(
            session=session,
            settings=settings,
            embedding_provider=embedding_provider,
            generation_provider=generation_provider,
            runtime=request.app.state.langchain_runtime,
        ).ask(knowledge_base_id, payload)
    return RagService(
        session=session,
        settings=settings,
        embedding_provider=embedding_provider,
        generation_provider=generation_provider,
    ).ask(knowledge_base_id, payload)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/retrieve",
    response_model=RetrievalResponse,
)
def debug_retrieval(
    knowledge_base_id: str,
    payload: RetrievalRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> RetrievalResponse:
    sources, elapsed_ms = RetrievalService(
        session=session,
        settings=settings,
        embedding_provider=embedding_provider,
    ).retrieve(
        knowledge_base_id=knowledge_base_id,
        query=payload.query,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
        source_document_ids=payload.source_document_ids,
    )
    return RetrievalResponse(
        query=payload.query,
        sources=[source_to_read(source) for source in sources],
        embedding_model=embedding_provider.model_name,
        elapsed_ms=elapsed_ms,
    )


@router.get("/rag/config", response_model=RagConfigurationRead)
def rag_configuration(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
    generation_queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> RagConfigurationRead:
    queue_stats = generation_queue.stats
    indexed_models = {
        value
        for value in session.scalars(
            select(DocumentChunk.embedding_model).where(
                DocumentChunk.embedding.is_not(None),
                DocumentChunk.indexed_at.is_not(None),
            )
        ).all()
        if isinstance(value, str) and value
    }
    embedding_status = str(getattr(embedding_provider, "load_status", "cold"))
    generation_status = str(getattr(generation_provider, "load_status", "cold"))
    models_ready = embedding_status == "ready" and generation_status == "ready"
    warmup_status = "ready" if models_ready else request.app.state.model_warmup.status
    return RagConfigurationRead(
        embedding_model=settings.embedding_model_name,
        generation_model=settings.generation_model_name,
        rag_engine=settings.rag_engine,
        quantization=settings.generation_quantization,
        model_device=str(request.app.state.model_device),
        embedding_model_cached=_model_is_cached(settings, settings.embedding_model_name),
        generation_model_cached=_model_is_cached(settings, settings.generation_model_name),
        model_warm=bool(
            getattr(embedding_provider, "is_loaded", False)
            and getattr(generation_provider, "is_loaded", False)
        ),
        embedding_model_status=embedding_status,
        generation_model_status=generation_status,
        warmup_status=warmup_status,
        vector_store=(
            "langchain-faiss" if settings.rag_engine == "langchain" else "relational-float32"
        ),
        top_k=settings.retrieval_top_k,
        candidate_pool=settings.retrieval_candidate_pool,
        similarity_threshold=settings.similarity_threshold,
        retrieval_strategy=(
            "langchain_faiss_similarity"
            if settings.rag_engine == "langchain"
            else "hybrid_dense_bm25_rerank"
        ),
        score_weights={
            "dense": settings.dense_score_weight,
            "lexical": settings.lexical_score_weight,
            "rerank": settings.rerank_score_weight,
        },
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        temperature=settings.generation_temperature,
        generation_top_k=settings.generation_top_k,
        top_p=settings.generation_top_p,
        maximum_new_tokens=settings.generation_max_new_tokens,
        repetition_penalty=settings.generation_repetition_penalty,
        do_sample=settings.generation_do_sample,
        maximum_context_characters=settings.max_context_characters,
        conversation_history_messages=settings.conversation_history_messages,
        runtime_profile=settings.runtime_profile,
        generation_queue_active=queue_stats.active,
        generation_queue_queued=queue_stats.queued,
        generation_timeout_seconds=settings.generation_timeout_seconds,
        embedding_reindex_required=bool(
            indexed_models - {settings.embedding_model_name}
        ),
    )


@router.post("/rag/warmup", status_code=status.HTTP_202_ACCEPTED)
def warm_models(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
) -> dict[str, str]:
    controller = request.app.state.model_warmup
    if controller.begin():
        background_tasks.add_task(
            controller.run,
            embedding_provider,
            generation_provider,
            settings,
        )
    return {"status": controller.status}


@router.post(
    "/chat-sessions",
    response_model=ChatSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_chat_session(
    payload: ChatSessionCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> ChatSessionRead:
    if KnowledgeBaseRepository(session).get(payload.knowledge_base_id) is None:
        raise NotFoundError("Knowledge base")
    value = ConversationRepository(session).create_session(payload.knowledge_base_id, payload.title)
    return ChatSessionRead.model_validate(value)


@router.get("/chat-sessions", response_model=ChatSessionList)
def list_chat_sessions(
    session: Annotated[Session, Depends(get_db_session)],
    knowledge_base_id: Annotated[str | None, Query()] = None,
) -> ChatSessionList:
    values = ConversationRepository(session).list_sessions(knowledge_base_id)
    return ChatSessionList(
        items=[ChatSessionRead.model_validate(value) for value in values],
        total=len(values),
    )


@router.get("/chat-sessions/{chat_session_id}", response_model=ChatSessionDetail)
def get_chat_session(
    chat_session_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> ChatSessionDetail:
    repository = ConversationRepository(session)
    value = repository.get_session(chat_session_id)
    if value is None:
        raise NotFoundError("Chat session")
    return ChatSessionDetail(
        **ChatSessionRead.model_validate(value).model_dump(),
        messages=[
            ChatMessageRead.model_validate(message)
            for message in repository.all_messages(chat_session_id)
        ],
    )


@router.delete("/chat-sessions/{chat_session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    chat_session_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    repository = ConversationRepository(session)
    value = repository.get_session(chat_session_id)
    if value is None:
        raise NotFoundError("Chat session")
    repository.delete_session(value)
