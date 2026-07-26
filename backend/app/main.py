from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai.generation_queue import GenerationQueue
from app.ai.hardware import resolve_model_device
from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.ai.langchain_engine.runtime import LangChainEngineRuntime
from app.ai.providers.huggingface import (
    HuggingFaceEmbeddingProvider,
    HuggingFaceGenerationProvider,
)
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import (
    AppError,
    ProcessingError,
    app_error_handler,
    http_error_handler,
    processing_error_handler,
    request_validation_handler,
)
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.media.transcription import (
    FasterWhisperTranscriptionProvider,
    TranscriptionProvider,
)
from app.models import Document, KnowledgeBase  # noqa: F401
from app.services.storage import LocalFileStorage


def create_app(
    settings: Settings | None = None,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    generation_provider: GenerationProvider | None = None,
    transcription_provider: TranscriptionProvider | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    engine = create_database_engine(runtime_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime_settings.storage_path.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.session_factory = session_factory
    app.state.file_storage = LocalFileStorage(
        runtime_settings.storage_path, runtime_settings.max_upload_bytes
    )
    configured_model_device = (
        resolve_model_device(runtime_settings.model_device)
        if embedding_provider is None or generation_provider is None
        else str(
            getattr(
                generation_provider,
                "device",
                getattr(embedding_provider, "device", "local"),
            )
        )
    )
    app.state.model_device = configured_model_device
    app.state.embedding_provider = embedding_provider or HuggingFaceEmbeddingProvider(
        model_name=runtime_settings.embedding_model_name,
        cache_path=runtime_settings.model_cache_path,
        device=configured_model_device,
        batch_size=runtime_settings.embedding_batch_size,
        local_files_only=runtime_settings.hf_local_files_only,
    )
    app.state.generation_provider = generation_provider or HuggingFaceGenerationProvider(
        model_name=runtime_settings.generation_model_name,
        cache_path=runtime_settings.model_cache_path,
        device=configured_model_device,
        local_files_only=runtime_settings.hf_local_files_only,
        fallback_model_name=runtime_settings.generation_fallback_model_name,
        quantization=runtime_settings.generation_quantization,
    )

    # LangChain runtime: in low-memory mode with force_wrapper, the
    # LangChain LLM adapter wraps the existing generation_provider instead
    # of loading a duplicate HuggingFace pipeline.
    app.state.langchain_runtime = (
        LangChainEngineRuntime(
            settings=runtime_settings,
            generation_provider=app.state.generation_provider,
            device=configured_model_device,
        )
        if runtime_settings.rag_engine == "langchain"
        else None
    )
    app.state.transcription_provider = transcription_provider or FasterWhisperTranscriptionProvider(
        model_name=runtime_settings.transcription_model_name,
        cache_path=runtime_settings.model_cache_path / "whisper",
        device=runtime_settings.transcription_device,
        compute_type=runtime_settings.transcription_compute_type,
        cpu_threads=runtime_settings.transcription_cpu_threads,
    )

    # ── Generation concurrency queue ─────────────────────────────────
    app.state.generation_queue = GenerationQueue(
        max_concurrent=runtime_settings.max_concurrent_generations,
        queue_timeout=runtime_settings.generation_queue_timeout_seconds,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(ProcessingError, processing_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.include_router(api_router, prefix=runtime_settings.api_prefix)

    # Mount static assets if compiled React build is present (Hugging Face Docker Space)
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="static_assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                raise StarletteHTTPException(status_code=404)
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
