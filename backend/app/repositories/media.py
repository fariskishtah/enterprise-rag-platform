from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.media import (
    MediaChapter,
    MediaExportRecord,
    MediaSource,
    MediaSummary,
    TranscriptSegment,
)


class MediaRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, media_source_id: str) -> MediaSource | None:
        return self.session.get(MediaSource, media_source_id)

    def add(self, media_source: MediaSource) -> MediaSource:
        self.session.add(media_source)
        self.session.commit()
        self.session.refresh(media_source)
        return media_source

    def list_for_knowledge_base(self, knowledge_base_id: str) -> list[MediaSource]:
        statement = (
            select(MediaSource)
            .where(MediaSource.knowledge_base_id == knowledge_base_id)
            .order_by(MediaSource.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def find_by_checksum(self, knowledge_base_id: str, checksum_sha256: str) -> MediaSource | None:
        return self.session.scalar(
            select(MediaSource).where(
                MediaSource.knowledge_base_id == knowledge_base_id,
                MediaSource.checksum_sha256 == checksum_sha256,
            )
        )

    def find_by_url(self, knowledge_base_id: str, url: str) -> MediaSource | None:
        return self.session.scalar(
            select(MediaSource).where(
                MediaSource.knowledge_base_id == knowledge_base_id,
                MediaSource.original_url == url,
            )
        )

    def replace_segments(self, media_source_id: str, segments: list[TranscriptSegment]) -> None:
        self.session.execute(
            delete(TranscriptSegment).where(TranscriptSegment.media_source_id == media_source_id)
        )
        self.session.add_all(segments)
        self.session.flush()

    def segments(
        self, media_source_id: str, *, offset: int = 0, limit: int = 5000
    ) -> list[TranscriptSegment]:
        return list(
            self.session.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.media_source_id == media_source_id)
                .order_by(TranscriptSegment.segment_index)
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def all_segments(self, media_source_id: str) -> list[TranscriptSegment]:
        return self.segments(media_source_id, limit=100000)

    def replace_chapters(self, media_source_id: str, chapters: list[MediaChapter]) -> None:
        self.session.execute(
            delete(MediaChapter).where(MediaChapter.media_source_id == media_source_id)
        )
        self.session.add_all(chapters)
        self.session.flush()

    def upsert_summary(self, summary: MediaSummary) -> MediaSummary:
        existing = self.session.scalar(
            select(MediaSummary).where(
                MediaSummary.media_source_id == summary.media_source_id,
                MediaSummary.summary_kind == summary.summary_kind,
            )
        )
        if existing is None:
            self.session.add(summary)
            self.session.flush()
            return summary
        existing.content = summary.content
        existing.structured_data = summary.structured_data
        existing.model_name = summary.model_name
        self.session.add(existing)
        self.session.flush()
        return existing

    def summary(self, media_source_id: str, kind: str = "intelligence") -> MediaSummary | None:
        return self.session.scalar(
            select(MediaSummary).where(
                MediaSummary.media_source_id == media_source_id,
                MediaSummary.summary_kind == kind,
            )
        )

    def record_export(self, media_source_id: str, export_kind: str, format_name: str) -> None:
        self.session.add(
            MediaExportRecord(
                media_source_id=media_source_id,
                export_kind=export_kind,
                format=format_name,
            )
        )
        self.session.commit()

    def delete(self, media_source: MediaSource) -> None:
        self.session.delete(media_source)
        self.session.commit()
