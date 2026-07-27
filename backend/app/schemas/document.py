from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, DocumentType


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    name: str
    document_type: DocumentType
    media_type: str
    size_bytes: int
    checksum_sha256: str
    status: DocumentStatus
    status_message: str | None
    processing_error: str | None
    extraction_warnings: list[str]
    extraction_metadata: dict[str, Any]
    page_count: int | None
    character_count: int
    chunk_count: int
    indexed_chunk_count: int
    processing_attempts: int
    embedding_model: str | None
    processing_started_at: datetime | None
    extraction_completed_at: datetime | None
    indexing_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime
    expires_at: datetime | None
    is_protected: bool


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int


class ExtractedSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section_index: int
    page_number: int | None
    heading: str | None
    text: str
    start_char: int
    end_char: int
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")


class DocumentExtractionRead(BaseModel):
    document_id: str
    filename: str
    document_type: DocumentType
    status: DocumentStatus
    page_count: int | None
    character_count: int
    extraction_completed_at: datetime | None
    warnings: list[str]
    error: str | None
    metadata: dict[str, Any]
    sections: list[ExtractedSectionRead]


class DocumentPreviewRead(BaseModel):
    document_id: str
    text: str
    offset: int
    returned_characters: int
    total_characters: int
    truncated: bool


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    knowledge_base_id: str
    chunk_index: int
    text: str
    page_number: int | None
    section_index: int | None
    start_char: int | None
    end_char: int | None
    character_count: int
    token_estimate: int
    extraction_metadata: dict[str, Any]
    embedding_model: str | None
    indexed_at: datetime | None


class DocumentChunkList(BaseModel):
    items: list[DocumentChunkRead]
    page: int
    page_size: int
    total: int
