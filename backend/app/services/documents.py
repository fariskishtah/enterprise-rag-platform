import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UploadValidationError
from app.document_processing.validation import CANONICAL_MEDIA_TYPES, document_type_for_filename
from app.models.document import Document, DocumentStatus
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.services.storage import LocalFileStorage


class DocumentService:
    def __init__(
        self,
        session: Session,
        storage: LocalFileStorage,
        *,
        langchain_pipeline: Any | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.documents = DocumentRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.langchain_pipeline = langchain_pipeline

    async def upload(self, knowledge_base_id: str, upload: UploadFile) -> Document:
        if self.knowledge_bases.get(knowledge_base_id) is None:
            raise NotFoundError("Knowledge base")

        original_name = Path(upload.filename or "").name
        if not original_name:
            raise UploadValidationError(
                code="missing_filename", message="The uploaded document must have a filename."
            )

        document_type = document_type_for_filename(original_name)
        document_id = str(uuid.uuid4())
        stored = await self.storage.save(
            upload=upload,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            document_type=document_type,
        )
        duplicate = self.documents.find_by_checksum(knowledge_base_id, stored.checksum_sha256)
        if duplicate is not None:
            self.storage.delete(stored.storage_key)
            raise ConflictError(
                code="duplicate_document",
                message=(
                    "This document is already stored in the selected knowledge base "
                    f"as '{duplicate.name}'."
                ),
            )

        document = Document(
            id=document_id,
            knowledge_base_id=knowledge_base_id,
            name=original_name,
            document_type=document_type,
            media_type=CANONICAL_MEDIA_TYPES[document_type],
            size_bytes=stored.size_bytes,
            checksum_sha256=stored.checksum_sha256,
            storage_key=stored.storage_key,
            status=DocumentStatus.UPLOADED,
            status_message="Stored and ready for processing.",
        )
        try:
            return self.documents.add(document)
        except Exception:
            self.session.rollback()
            self.storage.delete(stored.storage_key)
            raise

    def delete(self, document_id: str) -> None:
        document = self.documents.get(document_id)
        if document is None:
            raise NotFoundError("Document")
        storage_key = document.storage_key
        if self.langchain_pipeline is not None:
            self.langchain_pipeline.delete_document_vectors(
                document.knowledge_base_id,
                document.id,
            )
        self.documents.delete(document)
        self.storage.delete(storage_key)
