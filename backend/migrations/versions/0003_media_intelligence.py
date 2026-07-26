"""Add first-class media, transcription, summary, chapter, attempt, and export data.

Revision ID: 0003_media_intelligence
Revises: 0002_rag
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_media_intelligence"
down_revision: str | None = "0002_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("transcript_document_id", sa.String(length=36), nullable=True),
        sa.Column(
            "source_kind",
            sa.Enum(
                "UPLOAD",
                "PUBLIC_URL",
                "YOUTUBE",
                name="mediasourcekind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("media_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("source_platform", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=300), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("detected_language", sa.String(length=32), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("subtitle_source", sa.String(length=80), nullable=True),
        sa.Column("transcription_status", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "UPLOADED_OR_LINKED",
                "VALIDATING",
                "FETCHING_METADATA",
                "DOWNLOADING_OR_EXTRACTING_SUBTITLES",
                "EXTRACTING_AUDIO",
                "TRANSCRIBING",
                "TRANSCRIPT_READY",
                "CHUNKING",
                "EMBEDDING",
                "INDEXING",
                "SUMMARISING",
                "READY",
                "FAILED",
                name="mediaprocessingstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("status_message", sa.String(length=500), nullable=True),
        sa.Column("progress_stage", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("safe_error_message", sa.Text(), nullable=True),
        sa.Column("technical_error_message", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_attempts", sa.Integer(), nullable=False),
        sa.Column("ingestion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transcript_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transcript_document_id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint(
            "knowledge_base_id",
            "checksum_sha256",
            name="uq_media_sources_kb_checksum",
        ),
    )
    op.create_index("ix_media_sources_knowledge_base_id", "media_sources", ["knowledge_base_id"])
    op.create_index(
        "ix_media_sources_kb_status",
        "media_sources",
        ["knowledge_base_id", "status"],
    )

    op.create_table(
        "transcript_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_source_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "COMPLETE",
                "FAILED",
                name="transcriptjobstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("device", sa.String(length=30), nullable=False),
        sa.Column("compute_type", sa.String(length=30), nullable=False),
        sa.Column("forced_language", sa.String(length=32), nullable=True),
        sa.Column("detected_language", sa.String(length=32), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_source_id"], ["media_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_jobs_media_source_id", "transcript_jobs", ["media_source_id"])

    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("media_source_id", sa.String(length=36), nullable=False),
        sa.Column("transcript_job_id", sa.String(length=36), nullable=True),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_source_id"], ["media_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transcript_job_id"], ["transcript_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_source_id", "segment_index", name="uq_transcript_segment_index"),
    )
    op.create_index(
        "ix_transcript_segments_media_source_id",
        "transcript_segments",
        ["media_source_id"],
    )

    op.create_table(
        "media_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_source_id", sa.String(length=36), nullable=False),
        sa.Column("summary_kind", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_data", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_source_id"], ["media_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_source_id", "summary_kind", name="uq_media_summary_kind"),
    )
    op.create_index("ix_media_summaries_media_source_id", "media_summaries", ["media_source_id"])

    op.create_table(
        "media_chapters",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("media_source_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_source_id"], ["media_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_source_id", "chapter_index", name="uq_media_chapter_index"),
    )
    op.create_index("ix_media_chapters_media_source_id", "media_chapters", ["media_source_id"])

    op.create_table(
        "media_processing_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_source_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_stage", sa.String(length=60), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_source_id"], ["media_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_media_processing_attempts_media_source_id",
        "media_processing_attempts",
        ["media_source_id"],
    )

    op.create_table(
        "media_export_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_source_id", sa.String(length=36), nullable=False),
        sa.Column("export_kind", sa.String(length=40), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_source_id"], ["media_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_media_export_records_media_source_id",
        "media_export_records",
        ["media_source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_export_records_media_source_id", table_name="media_export_records")
    op.drop_table("media_export_records")
    op.drop_index(
        "ix_media_processing_attempts_media_source_id",
        table_name="media_processing_attempts",
    )
    op.drop_table("media_processing_attempts")
    op.drop_index("ix_media_chapters_media_source_id", table_name="media_chapters")
    op.drop_table("media_chapters")
    op.drop_index("ix_media_summaries_media_source_id", table_name="media_summaries")
    op.drop_table("media_summaries")
    op.drop_index("ix_transcript_segments_media_source_id", table_name="transcript_segments")
    op.drop_table("transcript_segments")
    op.drop_index("ix_transcript_jobs_media_source_id", table_name="transcript_jobs")
    op.drop_table("transcript_jobs")
    op.drop_index("ix_media_sources_kb_status", table_name="media_sources")
    op.drop_index("ix_media_sources_knowledge_base_id", table_name="media_sources")
    op.drop_table("media_sources")
