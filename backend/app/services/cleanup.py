"""Path-safe cleanup for expiring public-demo data and temporary files."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.document import Document, DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.media import MediaProcessingStatus, MediaSource
from app.services.storage import LocalFileStorage

logger = logging.getLogger(__name__)

ACTIVE_DOCUMENT_STATES = {
    DocumentStatus.VALIDATING,
    DocumentStatus.EXTRACTING,
    DocumentStatus.EXTRACTED,
    DocumentStatus.CHUNKING,
    DocumentStatus.EMBEDDING,
    DocumentStatus.VECTOR_INDEXING,
    DocumentStatus.INDEXED,
    DocumentStatus.PROCESSING,
}
ACTIVE_MEDIA_STATES = {
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


@dataclass
class CleanupResult:
    status: str
    completed_at: str
    dry_run: bool
    items: int
    bytes: int
    expired_records: int
    orphaned_files: int
    temporary_paths: int


class DemoCleanupService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.storage = LocalFileStorage(settings.storage_path, settings.max_upload_bytes)
        self.root = self.storage.root

    def run(self, *, dry_run: bool) -> CleanupResult:
        now = datetime.now(UTC)
        comparable_now = now
        protected_kb_ids = set(
            self.session.scalars(
                select(KnowledgeBase.id).where(KnowledgeBase.is_protected.is_(True))
            ).all()
        )
        expired_documents = list(
            self.session.scalars(
                select(Document).where(
                    Document.expires_at.is_not(None),
                    Document.expires_at <= comparable_now,
                    Document.is_protected.is_(False),
                    Document.knowledge_base_id.not_in(protected_kb_ids),
                    Document.status.not_in(ACTIVE_DOCUMENT_STATES),
                )
            ).all()
        )
        expired_media = list(
            self.session.scalars(
                select(MediaSource).where(
                    MediaSource.expires_at.is_not(None),
                    MediaSource.expires_at <= comparable_now,
                    MediaSource.is_protected.is_(False),
                    MediaSource.knowledge_base_id.not_in(protected_kb_ids),
                    MediaSource.status.not_in(ACTIVE_MEDIA_STATES),
                )
            ).all()
        )
        blocked_kb_ids = {
            value
            for value in self.session.scalars(
                select(Document.knowledge_base_id).where(
                    or_(
                        Document.is_protected.is_(True),
                        Document.status.in_(ACTIVE_DOCUMENT_STATES),
                    )
                )
            ).all()
        } | {
            value
            for value in self.session.scalars(
                select(MediaSource.knowledge_base_id).where(
                    or_(
                        MediaSource.is_protected.is_(True),
                        MediaSource.status.in_(ACTIVE_MEDIA_STATES),
                    )
                )
            ).all()
        }
        expired_knowledge_bases = list(
            self.session.scalars(
                select(KnowledgeBase).where(
                    KnowledgeBase.expires_at.is_not(None),
                    KnowledgeBase.expires_at <= comparable_now,
                    KnowledgeBase.is_protected.is_(False),
                    KnowledgeBase.id.not_in(blocked_kb_ids),
                )
            ).all()
        )

        expiring_kb_ids = {value.id for value in expired_knowledge_bases}
        all_documents = list(self.session.scalars(select(Document)).all())
        all_media = list(self.session.scalars(select(MediaSource)).all())
        record_paths: set[str] = {value.storage_key for value in all_documents}
        record_paths.update(value.storage_key for value in all_media if value.storage_key)
        deletion_keys = {
            value.storage_key
            for value in expired_documents
            if value.knowledge_base_id not in expiring_kb_ids
        }
        deletion_keys.update(
            value.storage_key
            for value in all_documents
            if value.knowledge_base_id in expiring_kb_ids
        )
        deletion_keys.update(
            value.storage_key
            for value in expired_media
            if value.storage_key and value.knowledge_base_id not in expiring_kb_ids
        )
        deletion_keys.update(
            value.storage_key
            for value in all_media
            if value.storage_key and value.knowledge_base_id in expiring_kb_ids
        )

        expired_records = (
            len(expired_knowledge_bases)
            + sum(value.knowledge_base_id not in expiring_kb_ids for value in expired_documents)
            + sum(value.knowledge_base_id not in expiring_kb_ids for value in expired_media)
        )
        if not dry_run:
            for value in expired_documents:
                if value.knowledge_base_id not in expiring_kb_ids:
                    self.session.delete(value)
            for value in expired_media:
                if value.knowledge_base_id not in expiring_kb_ids:
                    self.session.delete(value)
            for value in expired_knowledge_bases:
                self.session.delete(value)
            self.session.commit()

        removed_bytes = 0
        removed_items = 0
        for storage_key in sorted(deletion_keys):
            try:
                candidate = self.storage.resolve(storage_key)
            except ValueError:
                continue
            if candidate.is_file():
                removed_bytes += candidate.stat().st_size
                removed_items += 1
                if not dry_run:
                    candidate.unlink(missing_ok=True)

        orphan_count, orphan_bytes = self._clean_orphans(record_paths - deletion_keys, dry_run)
        temp_count, temp_bytes = self._clean_temporary_paths(dry_run)
        result = CleanupResult(
            status="ok",
            completed_at=now.isoformat(),
            dry_run=dry_run,
            items=removed_items + orphan_count + temp_count,
            bytes=removed_bytes + orphan_bytes + temp_bytes,
            expired_records=expired_records,
            orphaned_files=orphan_count,
            temporary_paths=temp_count,
        )
        if not dry_run:
            self._write_marker(result)
        logger.info(
            "Demo cleanup completed",
            extra={"enterprise_event": {"event": "demo_cleanup", **asdict(result)}},
        )
        return result

    def _clean_orphans(self, referenced: set[str], dry_run: bool) -> tuple[int, int]:
        count = 0
        size = 0
        cutoff = time.time() - self.settings.temp_file_retention_hours * 3600
        if not self.root.is_dir():
            return count, size
        for candidate in self.root.rglob("*"):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative = candidate.relative_to(self.root).as_posix()
            if relative.startswith((".processing/", ".operations/")) or relative in referenced:
                continue
            try:
                if candidate.stat().st_mtime > cutoff:
                    continue
                size += candidate.stat().st_size
                count += 1
                if not dry_run:
                    candidate.unlink(missing_ok=True)
            except OSError:
                continue
        return count, size

    def _clean_temporary_paths(self, dry_run: bool) -> tuple[int, int]:
        processing_root = self.root / ".processing"
        cutoff = time.time() - self.settings.temp_file_retention_hours * 3600
        active_ids = {
            value
            for value in self.session.scalars(
                select(MediaSource.id).where(MediaSource.status.in_(ACTIVE_MEDIA_STATES))
            ).all()
        }
        count = 0
        size = 0
        if not processing_root.is_dir():
            return count, size
        for candidate in processing_root.iterdir():
            try:
                if candidate.is_symlink() or candidate.stat().st_mtime > cutoff:
                    continue
                if any(candidate.name.startswith(f"{value}-") for value in active_ids):
                    continue
                path_size = sum(
                    value.stat().st_size
                    for value in candidate.rglob("*")
                    if value.is_file() and not value.is_symlink()
                ) if candidate.is_dir() else candidate.stat().st_size
                count += 1
                size += path_size
                if not dry_run:
                    if candidate.is_dir():
                        for value in sorted(candidate.rglob("*"), reverse=True):
                            if value.is_file() or value.is_symlink():
                                value.unlink(missing_ok=True)
                            elif value.is_dir():
                                value.rmdir()
                        candidate.rmdir()
                    else:
                        candidate.unlink(missing_ok=True)
            except OSError:
                continue
        return count, size

    def _write_marker(self, result: CleanupResult) -> None:
        directory = self.root / ".operations"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        marker = directory / "last-cleanup.json"
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(result)), encoding="utf-8")
        temporary.chmod(0o600)
        os.replace(temporary, marker)
