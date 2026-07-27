from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai.interfaces import EmbeddingProvider
from app.ai.vectorstores.relational import RelationalVectorStore
from app.core.config import Settings
from app.core.errors import NotFoundError, ProcessingError
from app.document_processing.chunking import TextChunker
from app.document_processing.extraction import ExtractedDocument, ExtractorRegistry
from app.document_processing.validation import validate_file_content
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentSection,
    DocumentStatus,
)
from app.repositories.documents import DocumentRepository
from app.services.storage import LocalFileStorage


class DocumentProcessingService:
    def __init__(
        self,
        *,
        session: Session,
        storage: LocalFileStorage,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        langchain_pipeline: Any | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.langchain_pipeline = langchain_pipeline
        self.documents = DocumentRepository(session)
        self.extractors = ExtractorRegistry()
        self.chunker = TextChunker(settings.chunk_size, settings.chunk_overlap)
        self.vector_store = RelationalVectorStore(session)

    def process(self, document_id: str) -> Document:
        document = self.documents.get(document_id)
        if document is None:
            raise NotFoundError("Document")

        document.processing_attempts += 1
        document.processing_started_at = datetime.now(UTC)
        document.processing_error = None
        document.extraction_warnings = []
        self._set_status(document, DocumentStatus.VALIDATING, "Validating stored document.")

        try:
            path = self.storage.resolve(document.storage_key)
            if not path.is_file():
                raise ProcessingError(
                    "The stored document file is missing.",
                    code="stored_file_missing",
                )
            validate_file_content(path, document.document_type)

            self.documents.delete_generated_content(document.id)
            document.chunk_count = 0
            document.indexed_chunk_count = 0
            document.indexing_completed_at = None
            document.embedding_model = None
            self.session.commit()

            self._set_status(
                document,
                DocumentStatus.EXTRACTING,
                "Extracting text and source structure.",
            )
            extracted = self.extractors.extract(path, document.document_type)
            if (
                extracted.page_count is not None
                and extracted.page_count > self.settings.max_document_pages
            ):
                raise ProcessingError(
                    "The document exceeds the public-demo page limit. "
                    "Upload a shorter document or split it into smaller files.",
                    code="document_page_limit_exceeded",
                )
            self._persist_extraction(document, extracted)

            self._set_status(
                document,
                DocumentStatus.CHUNKING,
                "Creating deterministic retrieval chunks.",
            )
            chunks = self._build_chunks(document, extracted)
            if not chunks:
                raise ProcessingError(
                    "No retrieval chunks could be created from the extracted document.",
                    code="empty_chunk_set",
                )
            self.session.add_all(chunks)
            document.chunk_count = len(chunks)
            self.session.commit()

            self._set_status(
                document,
                DocumentStatus.EMBEDDING,
                f"Generating embeddings with {self.embedding_provider.model_name}.",
            )
            embeddings = self.embedding_provider.embed_documents([chunk.text for chunk in chunks])

            self._set_status(
                document,
                DocumentStatus.VECTOR_INDEXING,
                "Persisting vectors for knowledge-base retrieval.",
            )
            indexed_count = self.vector_store.upsert(
                chunks,
                embeddings,
                model_name=self.embedding_provider.model_name,
            )
            if self.settings.rag_engine == "langchain":
                if self.langchain_pipeline is None:
                    from app.ai.langchain_engine.document_pipeline import (
                        LangChainDocumentPipeline,
                    )

                    self.langchain_pipeline = LangChainDocumentPipeline.from_settings(
                        self.settings,
                        device=str(getattr(self.embedding_provider, "device", "cpu")),
                    )
                from app.ai.langchain_engine.document_pipeline import DocumentIndexInput

                langchain_count = self.langchain_pipeline.index_document(
                    DocumentIndexInput(
                        path=path,
                        document_id=document.id,
                        knowledge_base_id=document.knowledge_base_id,
                        source_filename=document.name,
                        document_type=document.document_type.value,
                    ),
                    replace=True,
                )
                document.extraction_metadata = {
                    **document.extraction_metadata,
                    "langchain_chunk_count": langchain_count,
                    "langchain_vector_store": "FAISS",
                }
            document.indexed_chunk_count = indexed_count
            document.embedding_model = self.embedding_provider.model_name
            document.indexing_completed_at = datetime.now(UTC)
            self._set_status(
                document,
                DocumentStatus.INDEXED,
                f"Indexed {indexed_count} chunks.",
            )
            self._set_status(
                document,
                DocumentStatus.READY_FOR_CHAT,
                "Extraction and vector indexing completed.",
            )
            return document
        except ProcessingError as exc:
            self._fail(document, exc.message)
            return document
        except Exception:
            self._fail(
                document,
                "Processing failed unexpectedly. Review the document and retry.",
            )
            return document

    def _persist_extraction(self, document: Document, extracted: ExtractedDocument) -> None:
        sections = [
            DocumentSection(
                id=hashlib.sha256(
                    f"{document.id}:section:{section.section_index}".encode()
                ).hexdigest(),
                document_id=document.id,
                section_index=section.section_index,
                page_number=section.page_number,
                heading=section.heading,
                text=section.text,
                start_char=section.start_char,
                end_char=section.end_char,
                metadata_json=section.metadata,
            )
            for section in extracted.sections
        ]
        self.session.add_all(sections)
        document.extracted_text = extracted.full_text
        document.page_count = extracted.page_count
        document.character_count = extracted.character_count
        document.extraction_warnings = extracted.warnings
        document.extraction_metadata = extracted.metadata
        document.extraction_completed_at = datetime.now(UTC)
        self._set_status(
            document,
            DocumentStatus.EXTRACTED,
            f"Extracted {extracted.character_count} characters.",
        )

    def _build_chunks(
        self, document: Document, extracted: ExtractedDocument
    ) -> list[DocumentChunk]:
        values = self.chunker.chunk(
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            sections=extracted.sections,
        )
        return [
            DocumentChunk(
                id=value.id,
                document_id=value.document_id,
                knowledge_base_id=value.knowledge_base_id,
                chunk_index=value.chunk_index,
                text=value.text,
                page_number=value.page_number,
                section_index=value.section_index,
                start_char=value.start_char,
                end_char=value.end_char,
                character_count=value.character_count,
                token_estimate=value.token_estimate,
                extraction_metadata=value.metadata,
            )
            for value in values
        ]

    def _set_status(self, document: Document, status: DocumentStatus, message: str) -> None:
        document.status = status
        document.status_message = message
        self.session.add(document)
        self.session.commit()

    def _fail(self, document: Document, message: str) -> None:
        self.session.rollback()
        current = self.documents.get(document.id)
        if current is None:
            return
        current.status = DocumentStatus.FAILED
        current.status_message = message
        current.processing_error = message
        self.session.add(current)
        self.session.commit()
