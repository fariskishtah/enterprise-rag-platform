"""Demo Workspace automated seeding endpoint."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentType
from app.models.evaluation import EvaluationCase, EvaluationDataset, EvaluationRun
from app.models.feedback import UserFeedback
from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_bases import KnowledgeBaseRepository

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_demo_workspace(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    kb_repo = KnowledgeBaseRepository(session)
    existing_kb = session.scalar(
        select(KnowledgeBase).where(KnowledgeBase.name == "Demo Workspace")
    )
    if existing_kb:
        return {
            "status": "already_seeded",
            "knowledge_base_id": existing_kb.id,
            "message": "Demo Workspace is already loaded.",
        }

    kb = kb_repo.create("Demo Workspace", "Deterministic portfolio demo knowledge base.")

    # Seed Document 1: Policy Document
    doc1 = Document(
        knowledge_base_id=kb.id,
        name="Employee_Handbook_2026.pdf",
        document_type=DocumentType.PDF,
        media_type="application/pdf",
        size_bytes=1024 * 45,
        checksum_sha256="demo-checksum-1",
        status=DocumentStatus.READY_FOR_CHAT,
        character_count=1200,
        chunk_count=3,
        indexed_chunk_count=3,
    )
    session.add(doc1)
    session.flush()

    chunks1 = [
        DocumentChunk(
            document_id=doc1.id,
            knowledge_base_id=kb.id,
            chunk_index=0,
            text=(
                "Employee Remote Work Policy: Employees may work remotely up to two days "
                "per week with manager approval. Core operating hours are 09:00 to 17:00 EST."
            ),
            page_number=1,
            section_index=0,
            character_count=160,
        ),
        DocumentChunk(
            document_id=doc1.id,
            knowledge_base_id=kb.id,
            chunk_index=1,
            text=(
                "Expense Reimbursement Rules: Travel expenses exceeding $100 require "
                "pre-approval. Receipts must be submitted within 30 days of purchase."
            ),
            page_number=2,
            section_index=1,
            character_count=155,
        ),
        DocumentChunk(
            document_id=doc1.id,
            knowledge_base_id=kb.id,
            chunk_index=2,
            text=(
                "Paid Time Off (PTO): Full-time employees accrue 20 days of paid vacation "
                "per calendar year. Up to 5 unused PTO days may roll over to the following year."
            ),
            page_number=3,
            section_index=2,
            character_count=165,
        ),
    ]
    session.add_all(chunks1)

    # Seed Document 2: Arabic Document
    doc2 = Document(
        knowledge_base_id=kb.id,
        name="Arabic_Corporate_Policy.txt",
        document_type=DocumentType.TXT,
        media_type="text/plain",
        size_bytes=1024 * 20,
        checksum_sha256="demo-checksum-2",
        status=DocumentStatus.READY_FOR_CHAT,
        character_count=800,
        chunk_count=2,
        indexed_chunk_count=2,
    )
    session.add(doc2)
    session.flush()

    chunks2 = [
        DocumentChunk(
            document_id=doc2.id,
            knowledge_base_id=kb.id,
            chunk_index=0,
            text=(
                "سياسة العمل عن بُعد: يُسمح للموظفين بالعمل عن بُعد لمدة يومين في الأسبوع "
                "بعد الحصول على موافقة المدير المباشر. ساعات العمل الأساسية هي 9-5."
            ),
            page_number=1,
            section_index=0,
            character_count=170,
        ),
        DocumentChunk(
            document_id=doc2.id,
            knowledge_base_id=kb.id,
            chunk_index=1,
            text=(
                "الإجازات السنوية المدفوعة: يحق للموظفين الحصول على 20 يوماً إجازة سنوية "
                "مدفوعة الأجر سنوياً. يمكن تدويل 5 أيام فقط للعام التالي."
            ),
            page_number=2,
            section_index=1,
            character_count=140,
        ),
    ]
    session.add_all(chunks2)

    # Seed Evaluation Dataset & Cases
    eval_dataset = EvaluationDataset(
        knowledge_base_id=kb.id,
        name="Core Policy Benchmark",
        description="Ground-truth test cases for policy Q&A",
        case_count=2,
    )
    session.add(eval_dataset)
    session.flush()

    case1 = EvaluationCase(
        dataset_id=eval_dataset.id,
        question="How many remote work days are allowed per week?",
        expected_answer="Up to two days per week with manager approval.",
        is_supported=True,
    )
    case2 = EvaluationCase(
        dataset_id=eval_dataset.id,
        question="كم يوماً يُسمح بالعمل عن بُعد أسبوعياً؟",
        expected_answer="يُسمح بالعمل عن بُعد لمدة يومين في الأسبوع.",
        language="ar",
        is_supported=True,
    )
    session.add_all([case1, case2])

    # Seed Evaluation Run
    eval_run = EvaluationRun(
        dataset_id=eval_dataset.id,
        engine="custom",
        model_name="Qwen2.5-0.5B-Instruct",
        total_cases=2,
        passed_cases=2,
        failed_cases=0,
        correctness_rate=1.0,
        faithfulness_rate=0.98,
        citation_accuracy=0.95,
        median_latency_ms=210.0,
        p95_latency_ms=350.0,
    )
    session.add(eval_run)

    # Seed Sample Feedback
    fb1 = UserFeedback(
        knowledge_base_id=kb.id,
        question="What is the travel expense pre-approval limit?",
        answer="Travel expenses exceeding $100 require pre-approval.",
        rating="helpful",
        category="accurate",
        latency_ms=180.0,
    )
    session.add(fb1)

    kb.document_count = 2
    session.commit()

    return {
        "status": "seeded",
        "knowledge_base_id": kb.id,
        "message": "Demo Workspace and datasets seeded successfully.",
    }
