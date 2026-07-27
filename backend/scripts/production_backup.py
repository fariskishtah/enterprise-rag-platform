#!/usr/bin/env python3
"""Create, verify, and restore production backups without copying secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from app.core.config import Settings, get_settings

SAFE_ENVIRONMENT_KEYS = (
    "ENTERPRISE_RAG_ACCESS_MODE",
    "ENTERPRISE_RAG_DATABASE_URL",
    "ENTERPRISE_RAG_STORAGE_PATH",
    "ENTERPRISE_RAG_MODEL_CACHE_PATH",
    "ENTERPRISE_RAG_RUNTIME_PROFILE",
    "ENTERPRISE_RAG_MAX_UPLOAD_MB",
    "ENTERPRISE_RAG_MAX_DOCUMENT_PAGES",
    "ENTERPRISE_RAG_MAX_MEDIA_DURATION_MINUTES",
    "ENTERPRISE_RAG_MAX_FILES_PER_KNOWLEDGE_BASE",
    "ENTERPRISE_RAG_MAX_KNOWLEDGE_BASES",
    "ENTERPRISE_RAG_MAX_CONCURRENT_HEAVY_OPERATIONS",
    "ENTERPRISE_RAG_DEMO_DATA_RETENTION_HOURS",
    "ENTERPRISE_RAG_SESSION_SECRET",
    "ENTERPRISE_RAG_DEMO_PASSWORD_HASH",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def database_path(settings: Settings) -> Path:
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        raise RuntimeError("Production backup currently requires the configured SQLite database.")
    return Path(settings.database_url.removeprefix(prefix)).resolve()


def safe_archive_member(member: tarfile.TarInfo) -> bool:
    path = PurePosixPath(member.name)
    return not (
        path.is_absolute()
        or ".." in path.parts
        or member.issym()
        or member.islnk()
        or member.isdev()
    )


def verify_backup(backup: Path) -> dict[str, object]:
    backup = backup.resolve()
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise RuntimeError("Backup manifest does not contain a valid file map.")
    for name, expected in files.items():
        path = backup / str(name)
        if not path.is_file() or digest(path) != expected:
            raise RuntimeError(f"Backup verification failed for {name}.")
    archive = backup / "application-data.tar.gz"
    with tarfile.open(archive, "r:gz") as value:
        if any(not safe_archive_member(member) for member in value.getmembers()):
            raise RuntimeError("Backup archive contains an unsafe path or link.")
    return manifest


def create_backup(settings: Settings, destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.chmod(0o700)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = destination / f"enterprise-rag-{timestamp}"
    backup.mkdir(mode=0o700)
    source_database = database_path(settings)
    if not source_database.is_file():
        raise RuntimeError("The configured SQLite database does not exist.")

    copied_database = backup / "enterprise_rag.db"
    with sqlite3.connect(source_database) as source, sqlite3.connect(copied_database) as target:
        source.backup(target)
    copied_database.chmod(0o600)

    archive = backup / "application-data.tar.gz"
    storage = settings.storage_path.resolve()
    storage.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as output:
        for path in sorted(storage.rglob("*")):
            if path.is_symlink() or path == archive:
                continue
            output.add(path, arcname=path.relative_to(storage).as_posix(), recursive=False)
    archive.chmod(0o600)

    environment_template = backup / "deployment.env.template"
    environment_template.write_text(
        "# Secret values are intentionally blank. Restore them from the secret manager.\n"
        + "\n".join(f"{key}=" for key in SAFE_ENVIRONMENT_KEYS)
        + "\n",
        encoding="utf-8",
    )
    environment_template.chmod(0o600)
    manifest = {
        "backup_id": backup.name,
        "created_at": datetime.now(UTC).isoformat(),
        "application_version": settings.app_version,
        "git_commit": settings.git_commit,
        "image_id": os.environ.get("ENTERPRISE_RAG_IMAGE_ID"),
        "runtime_profile": settings.runtime_profile,
        "files": {
            copied_database.name: digest(copied_database),
            archive.name: digest(archive),
            environment_template.name: digest(environment_template),
        },
    }
    manifest_path = backup / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    manifest_path.chmod(0o600)
    verify_backup(backup)
    _record_last_backup(settings.storage_path, backup.name)
    _expire_old_backups(destination, settings.backup_retention_days, keep=backup)
    return backup


def _expire_old_backups(destination: Path, retention_days: int, *, keep: Path) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    for candidate in destination.glob("enterprise-rag-????????T??????Z"):
        if candidate == keep or not candidate.is_dir() or candidate.is_symlink():
            continue
        modified = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
        if modified < cutoff:
            shutil.rmtree(candidate)


def _record_last_backup(storage_path: Path, backup_id: str) -> None:
    directory = storage_path.resolve() / ".operations"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    marker = directory / "last-backup.json"
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "status": "ok",
                "completed_at": datetime.now(UTC).isoformat(),
                "backup_id": backup_id,
            }
        ),
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    os.replace(temporary, marker)


def restore_backup(settings: Settings, backup: Path, *, confirmed: bool) -> None:
    if not confirmed:
        raise RuntimeError("Restore requires --confirm after a separate pre-restore backup.")
    backup = backup.expanduser().resolve()
    verify_backup(backup)
    target_database = database_path(settings)
    target_database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target_database.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".enterprise-rag-restore-",
        dir=target_database.parent,
    )
    os.close(descriptor)
    temporary_database = Path(temporary_name)
    try:
        shutil.copyfile(backup / "enterprise_rag.db", temporary_database)
        temporary_database.chmod(0o600)
        with sqlite3.connect(temporary_database) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise RuntimeError("Restored SQLite database did not pass integrity_check.")
        os.replace(temporary_database, target_database)
    finally:
        temporary_database.unlink(missing_ok=True)

    storage = settings.storage_path.resolve()
    storage.mkdir(mode=0o700, parents=True, exist_ok=True)
    storage.chmod(0o700)
    archive_paths: set[Path] = set()
    with tarfile.open(backup / "application-data.tar.gz", "r:gz") as archive:
        for member in archive.getmembers():
            if not safe_archive_member(member):
                raise RuntimeError("Backup archive contains an unsafe path or link.")
            destination = (storage / member.name).resolve()
            if destination != storage and storage not in destination.parents:
                raise RuntimeError("Backup archive resolves outside configured storage.")
            archive_paths.add(destination)
            if member.isdir():
                destination.mkdir(mode=0o700, parents=True, exist_ok=True)
            elif member.isfile():
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError("Backup archive contains an unreadable file.")
                with source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
                destination.chmod(0o600)
    for existing in sorted(storage.rglob("*"), key=lambda path: len(path.parts), reverse=True):
        if existing == storage / ".operations" or (storage / ".operations") in existing.parents:
            continue
        if existing not in archive_paths:
            if existing.is_file() or existing.is_symlink():
                existing.unlink(missing_ok=True)
            elif existing.is_dir():
                existing.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--destination", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("backup", type=Path)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("--confirm", action="store_true")
    arguments = parser.parse_args()
    settings = get_settings()
    if arguments.action == "backup":
        path = create_backup(settings, arguments.destination or settings.backup_dir)
        print(path)
    elif arguments.action == "verify":
        print(json.dumps(verify_backup(arguments.backup), sort_keys=True))
    else:
        restore_backup(settings, arguments.backup, confirmed=arguments.confirm)
        print("Restore completed and permissions validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
