import asyncio
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
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
from app.ai.warmup import ModelWarmupController
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
from app.core.logging import configure_json_logging
from app.core.middleware import (
    AccessControlMiddleware,
    LoginAttemptLimiter,
    RateLimitMiddleware,
    RequestBodyLimitMiddleware,
    RequestContextMiddleware,
    UploadConcurrencyMiddleware,
)
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.media.transcription import (
    FasterWhisperTranscriptionProvider,
    TranscriptionProvider,
)
from app.models import Document, KnowledgeBase  # noqa: F401
from app.services.media import prepare_runtime_ytdlp_cookie
from app.services.storage import LocalFileStorage


def create_app(
    settings: Settings | None = None,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    generation_provider: GenerationProvider | None = None,
    transcription_provider: TranscriptionProvider | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_json_logging()
    engine = create_database_engine(runtime_settings.database_url)
    session_factory = create_session_factory(engine)
    warmup_controller = ModelWarmupController()
    warmup_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal warmup_task
        runtime_settings.storage_path.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
        with suppress(ProcessingError):
            prepare_runtime_ytdlp_cookie(runtime_settings.ytdlp_cookies_file)
        if runtime_settings.warm_models_on_startup and warmup_controller.begin():
            async def warm_models() -> None:
                try:
                    slot = await app.state.generation_queue.acquire()
                    await app.state.generation_queue.execute(
                        slot,
                        lambda: warmup_controller.run(
                            app.state.embedding_provider,
                            app.state.generation_provider,
                            runtime_settings,
                        ),
                        timeout=(
                            runtime_settings.model_load_timeout_seconds
                            + runtime_settings.generation_timeout_seconds
                        ),
                    )
                except Exception:
                    warmup_controller.fail()

            warmup_task = asyncio.create_task(warm_models())
        yield
        if warmup_task is not None and not warmup_task.done():
            warmup_task.cancel()
        engine.dispose()

    app = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.engine = engine
    app.state.started_at = time.time()
    app.state.session_factory = session_factory
    app.state.login_limiter = LoginAttemptLimiter(
        runtime_settings.login_max_attempts,
        runtime_settings.login_lockout_minutes * 60,
    )
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
    if configured_model_device == "cpu" and (
        embedding_provider is None or generation_provider is None
    ):
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
        os.environ.setdefault(
            "TOKENIZERS_PARALLELISM",
            str(runtime_settings.tokenizer_parallelism).lower(),
        )
        try:
            import torch

            torch.set_num_threads(runtime_settings.torch_num_threads)
            with suppress(RuntimeError):
                torch.set_num_interop_threads(runtime_settings.torch_num_interop_threads)
        except ImportError:
            pass
    app.state.embedding_provider = embedding_provider or HuggingFaceEmbeddingProvider(
        model_name=runtime_settings.embedding_model_name,
        cache_path=runtime_settings.model_cache_path,
        device=configured_model_device,
        batch_size=runtime_settings.embedding_batch_size,
        local_files_only=runtime_settings.hf_local_files_only,
        query_cache_size=runtime_settings.query_embedding_cache_size,
    )
    app.state.generation_provider = generation_provider or HuggingFaceGenerationProvider(
        model_name=runtime_settings.generation_model_name,
        cache_path=runtime_settings.model_cache_path,
        device=configured_model_device,
        local_files_only=runtime_settings.hf_local_files_only,
        fallback_model_name=runtime_settings.generation_fallback_model_name,
        quantization=runtime_settings.generation_quantization,
        maximum_generation_seconds=runtime_settings.generation_timeout_seconds,
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
        num_workers=runtime_settings.transcription_num_workers,
        beam_size=runtime_settings.transcription_beam_size,
    )
    app.state.model_warmup = warmup_controller

    # ── Generation concurrency queue ─────────────────────────────────
    app.state.generation_queue = GenerationQueue(
        max_concurrent=runtime_settings.max_concurrent_heavy_operations,
        queue_timeout=runtime_settings.generation_queue_timeout_seconds,
        max_queue_size=runtime_settings.heavy_queue_max_size,
    )

    app.add_middleware(AccessControlMiddleware, settings=runtime_settings)
    app.add_middleware(RateLimitMiddleware, settings=runtime_settings)
    app.add_middleware(UploadConcurrencyMiddleware, settings=runtime_settings)
    app.add_middleware(RequestBodyLimitMiddleware, settings=runtime_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
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
            static_root = static_dir.resolve()
            file_path = (static_root / full_path).resolve()
            if static_root in file_path.parents and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(static_root / "index.html")

    return app


app = create_app()
