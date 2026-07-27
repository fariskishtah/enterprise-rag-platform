"""Deterministic sample-workspace seeding without fabricated evaluation results."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.generation_queue import GenerationQueue
from app.ai.interfaces import EmbeddingProvider
from app.ai.vectorstores.relational import RelationalVectorStore
from app.api.dependencies import (
    get_db_session,
    get_embedding_provider,
    get_file_storage,
    get_generation_queue,
    get_runtime_settings,
)
from app.core.config import Settings
from app.core.errors import (
    GenerationQueueFullError,
    GenerationTimeoutError,
    UploadValidationError,
)
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentSection,
    DocumentStatus,
    DocumentType,
)
from app.models.evaluation import EvaluationCase, EvaluationDataset
from app.models.knowledge_base import KnowledgeBase
from app.services.lifecycle import demo_expiry
from app.services.storage import LocalFileStorage

router = APIRouter(prefix="/demo", tags=["demo"])

ENGLISH_SAMPLE = (
    "Employee Remote Work Policy: Employees may work remotely up to two days per week "
    "with manager approval. Core operating hours are 09:00 to 17:00 EST.",
    "Expense Reimbursement Rules: Travel expenses exceeding $100 require pre-approval. "
    "Receipts must be submitted within 30 days of purchase.",
    "Paid Time Off (PTO): Full-time employees accrue 20 days of paid vacation per calendar "
    "year. Up to 5 unused PTO days may roll over to the following year.",
)
ARABIC_SAMPLE = (
    "سياسة العمل عن بُعد: يُسمح للموظفين بالعمل عن بُعد لمدة يومين في الأسبوع بعد "
    "الحصول على موافقة المدير المباشر. ساعات العمل الأساسية هي 9-5.",
    "الإجازات السنوية المدفوعة: يحق للموظفين الحصول على 20 يوماً إجازة سنوية مدفوعة "
    "الأجر سنوياً. يمكن ترحيل 5 أيام فقط للعام التالي.",
)


def _seed_document(
    *,
    knowledge_base_id: str,
    name: str,
    sections: tuple[str, ...],
    storage: LocalFileStorage,
    expires_at: datetime | None,
) -> tuple[Document, list[DocumentSection], list[DocumentChunk], str]:
    document_id = str(uuid.uuid4())
    content = "\n\n".join(sections)
    encoded = content.encode("utf-8")
    storage_key = f"{knowledge_base_id}/{document_id}.txt"
    destination = storage.resolve(storage_key)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.parent.chmod(0o700)
    with destination.open("xb") as output:
        output.write(encoded)
    destination.chmod(0o600)

    now = datetime.now(UTC)
    document = Document(
        id=document_id,
        knowledge_base_id=knowledge_base_id,
        name=name,
        document_type=DocumentType.TXT,
        media_type="text/plain",
        size_bytes=len(encoded),
        checksum_sha256=hashlib.sha256(encoded).hexdigest(),
        storage_key=storage_key,
        status=DocumentStatus.READY_FOR_CHAT,
        status_message="Indexed sample content ready for grounded questions.",
        extracted_text=content,
        character_count=len(content),
        chunk_count=len(sections),
        indexed_chunk_count=len(sections),
        extraction_completed_at=now,
        indexing_completed_at=now,
        expires_at=expires_at,
        extraction_metadata={"seeded_sample": True},
    )
    section_models: list[DocumentSection] = []
    chunk_models: list[DocumentChunk] = []
    cursor = 0
    for index, text in enumerate(sections):
        end = cursor + len(text)
        section_models.append(
            DocumentSection(
                id=hashlib.sha256(f"{document_id}:section:{index}".encode()).hexdigest(),
                document_id=document_id,
                section_index=index,
                page_number=None,
                heading=text.split(":", 1)[0],
                text=text,
                start_char=cursor,
                end_char=end,
                metadata_json={"seeded_sample": True},
            )
        )
        chunk_models.append(
            DocumentChunk(
                id=hashlib.sha256(f"{document_id}:chunk:{index}".encode()).hexdigest(),
                document_id=document_id,
                knowledge_base_id=knowledge_base_id,
                chunk_index=index,
                text=text,
                page_number=None,
                section_index=index,
                start_char=cursor,
                end_char=end,
                character_count=len(text),
                token_estimate=max(1, (len(text) + 3) // 4),
                extraction_metadata={"seeded_sample": True},
            )
        )
        cursor = end + 2
    return document, section_models, chunk_models, storage_key


def _seed_workspace(
    session: Session,
    settings: Settings,
    storage: LocalFileStorage,
    embedding_provider: EmbeddingProvider,
) -> dict[str, Any]:
    existing = session.scalar(
        select(KnowledgeBase).where(KnowledgeBase.name == "Demo Workspace")
    )
    if existing is not None:
        return {
            "status": "already_seeded",
            "knowledge_base_id": existing.id,
            "message": "The sample workspace is already loaded.",
        }
    count = session.scalar(select(func.count(KnowledgeBase.id))) or 0
    if count >= settings.max_knowledge_bases:
        raise UploadValidationError(
            code="knowledge_base_quota_exceeded",
            message=(
                "The public-demo knowledge-base limit has been reached. Remove an existing "
                "knowledge base before loading the sample workspace."
            ),
        )

    all_passages = [*ENGLISH_SAMPLE, *ARABIC_SAMPLE]
    embeddings = embedding_provider.embed_documents(all_passages)
    knowledge_base_id = str(uuid.uuid4())
    expires_at = demo_expiry(settings.demo_data_retention_hours)
    storage_keys: list[str] = []
    try:
        first, first_sections, first_chunks, first_key = _seed_document(
            knowledge_base_id=knowledge_base_id,
            name="Employee_Handbook_2026.txt",
            sections=ENGLISH_SAMPLE,
            storage=storage,
            expires_at=expires_at,
        )
        storage_keys.append(first_key)
        second, second_sections, second_chunks, second_key = _seed_document(
            knowledge_base_id=knowledge_base_id,
            name="Arabic_Corporate_Policy.txt",
            sections=ARABIC_SAMPLE,
            storage=storage,
            expires_at=expires_at,
        )
        storage_keys.append(second_key)

        knowledge_base = KnowledgeBase(
            id=knowledge_base_id,
            name="Demo Workspace",
            description="Deterministic sample content for product evaluation.",
            expires_at=expires_at,
        )
        session.add(knowledge_base)
        session.add_all([first, second, *first_sections, *second_sections])
        chunks = [*first_chunks, *second_chunks]
        session.add_all(chunks)
        RelationalVectorStore(session).upsert(
            chunks,
            embeddings,
            model_name=embedding_provider.model_name,
        )
        first.embedding_model = embedding_provider.model_name
        second.embedding_model = embedding_provider.model_name

        evaluation = EvaluationDataset(
            knowledge_base_id=knowledge_base_id,
            name="Core Policy Benchmark",
            description="Sample questions; run results are generated only on demand.",
            case_count=2,
        )
        session.add(evaluation)
        session.flush()
        session.add_all(
            [
                EvaluationCase(
                    dataset_id=evaluation.id,
                    question="How many remote work days are allowed per week?",
                    expected_answer="Up to two days per week with manager approval.",
                    is_supported=True,
                ),
                EvaluationCase(
                    dataset_id=evaluation.id,
                    question="كم يوماً يُسمح بالعمل عن بُعد أسبوعياً؟",
                    expected_answer="يُسمح بالعمل عن بُعد لمدة يومين في الأسبوع.",
                    language="ar",
                    is_supported=True,
                ),
            ]
        )
        session.commit()
    except Exception:
        session.rollback()
        for storage_key in storage_keys:
            storage.delete(storage_key)
        raise
    return {
        "status": "seeded",
        "knowledge_base_id": knowledge_base_id,
        "message": "The sample workspace and unscored evaluation cases are ready.",
    }


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_demo_workspace(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> dict[str, Any]:
    try:
        slot = await queue.acquire(timeout=settings.generation_queue_timeout_seconds)
    except TimeoutError as exc:
        raise GenerationQueueFullError(
            "The server is busy with another AI task. Retry loading the sample shortly."
        ) from exc
    try:
        return await queue.execute(
            slot,
            lambda: _seed_workspace(session, settings, storage, embedding_provider),
            timeout=settings.media_processing_timeout_seconds,
        )
    except TimeoutError as exc:
        raise GenerationTimeoutError(
            "Loading the sample workspace timed out. Retry after the model is available."
        ) from exc
