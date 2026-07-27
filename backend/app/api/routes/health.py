from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from app.core.errors import error_payload

router = APIRouter(tags=["health"])


@router.get("/health", summary="Lightweight process liveness check")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _writable_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".readiness-", dir=path, delete=True) as probe:
            probe.write(b"ready")
            probe.flush()
        return True
    except OSError:
        return False


def _schema_is_current(engine: object) -> bool:
    required = {
        "knowledge_bases": {"id", "created_at", "last_accessed_at", "expires_at"},
        "documents": {"id", "storage_key", "last_accessed_at", "expires_at"},
        "media_sources": {"id", "status", "last_accessed_at", "expires_at"},
    }
    database = inspect(engine)
    tables = set(database.get_table_names())
    columns_current = all(
        table in tables
        and columns <= {value["name"] for value in database.get_columns(table)}
        for table, columns in required.items()
    )
    if not columns_current:
        return False
    if "alembic_version" in tables:
        with engine.connect() as connection:  # type: ignore[attr-defined]
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return revision == "0004_public_demo_lifecycle"
    # Local/test databases created directly from SQLAlchemy metadata have no
    # Alembic table; the required current columns remain authoritative there.
    return True


def _readiness(request: Request) -> tuple[dict[str, Any], bool]:
    settings = request.app.state.settings
    checks: dict[str, bool] = {}
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    try:
        checks["schema"] = _schema_is_current(request.app.state.engine)
    except Exception:
        checks["schema"] = False
    checks["storage"] = _writable_directory(settings.storage_path)
    checks["model_cache"] = _writable_directory(settings.model_cache_path)
    checks["index_path"] = _writable_directory(settings.langchain_index_path)
    ready = all(checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "ordinary_requests_accepted": ready,
    }, ready


@router.get(
    "/readiness",
    summary="Database, schema, and storage readiness",
    response_model=None,
)
def readiness(request: Request) -> dict[str, Any] | JSONResponse:
    payload, ready = _readiness(request)
    if ready:
        return payload
    return JSONResponse(
        status_code=503,
        content=error_payload(
            "service_not_ready",
            "The service is alive but a required database or storage check failed.",
            payload,
        ),
    )


@router.get("/ready", summary="Backward-compatible readiness alias", response_model=None)
def ready(request: Request) -> dict[str, Any] | JSONResponse:
    _payload, is_ready = _readiness(request)
    if is_ready:
        return {"status": "ready"}
    return JSONResponse(
        status_code=503,
        content=error_payload(
            "service_not_ready",
            "The service is alive but a required database or storage check failed.",
        ),
    )


def _directory_size(path: Path) -> int:
    total = 0
    try:
        for value in path.rglob("*"):
            if value.is_file() and not value.is_symlink():
                total += value.stat().st_size
    except OSError:
        return total
    return total


def _operation_result(storage_path: Path, name: str) -> dict[str, Any] | None:
    marker = storage_path / ".operations" / f"last-{name}.json"
    try:
        if not marker.is_file() or marker.stat().st_size > 16384:
            return None
        value = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return None
        allowed = {"status", "completed_at", "items", "bytes", "dry_run", "backup_id"}
        return {key: value[key] for key in allowed if key in value}
    except (OSError, json.JSONDecodeError):
        return None


@router.get("/operations/status", summary="Protected operational status without secrets")
def operations_status(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    queue = request.app.state.generation_queue.stats
    storage_path = settings.storage_path
    storage_path.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(storage_path)
    embedding_state = str(getattr(request.app.state.embedding_provider, "load_status", "cold"))
    generation_state = str(getattr(request.app.state.generation_provider, "load_status", "cold"))
    transcription_state = str(
        getattr(request.app.state.transcription_provider, "load_status", "cold")
    )
    if queue.active:
        generation_state = "busy"
        if transcription_state == "ready":
            transcription_state = "busy"
    readiness_payload, readiness_ok = _readiness(request)
    database_ready = bool(
        readiness_payload["checks"]["database"]
        and readiness_payload["checks"]["schema"]
    )
    return {
        "application": {
            "version": settings.app_version,
            "git_commit": settings.git_commit,
            "runtime_profile": settings.runtime_profile,
            "uptime_seconds": round(time.time() - request.app.state.started_at, 1),
        },
        "database": {
            "status": "ready" if database_ready else "not_ready",
            "checks": readiness_payload["checks"],
        },
        "storage": {
            "used_bytes": _directory_size(storage_path),
            "free_disk_bytes": disk.free,
            "total_disk_bytes": disk.total,
        },
        "models": {
            "embeddings": embedding_state,
            "generation": generation_state,
            "transcription": transcription_state,
        },
        "heavy_operations": {
            "active": queue.active,
            "queued": queue.queued,
            "capacity": queue.capacity,
            "queue_capacity": queue.queue_capacity,
        },
        "limits": {
            "upload_mb": settings.max_upload_bytes // (1024 * 1024),
            "document_pages": settings.max_document_pages,
            "media_duration_minutes": settings.max_media_duration_seconds // 60,
            "files_per_knowledge_base": settings.max_files_per_knowledge_base,
            "knowledge_bases": settings.max_knowledge_bases,
            "concurrent_uploads": settings.max_concurrent_uploads,
            "demo_retention_hours": settings.demo_data_retention_hours,
        },
        "last_cleanup": _operation_result(storage_path, "cleanup"),
        "last_backup": _operation_result(storage_path, "backup"),
        "ordinary_requests_accepted": readiness_ok,
    }
