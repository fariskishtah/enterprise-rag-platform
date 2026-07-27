"""Evaluation Dashboard routes for datasets, benchmark runs, and metrics."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.generation_queue import GenerationQueue
from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.api.dependencies import (
    get_db_session,
    get_embedding_provider,
    get_generation_provider,
    get_generation_queue,
    get_runtime_settings,
)
from app.core.config import Settings
from app.core.errors import GenerationQueueFullError, GenerationTimeoutError
from app.models.evaluation import EvaluationDataset, EvaluationRun
from app.services.evaluation import EvaluationService
from app.services.rag import RagService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


class DatasetCreate(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class CaseCreate(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=36)
    question: str = Field(min_length=2, max_length=4000)
    expected_answer: str | None = Field(default=None, max_length=8000)
    expected_citations: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(
        default_factory=list,
        max_length=50,
    )
    language: str = Field(default="en", pattern="^(ar|en)$")
    is_supported: bool = True


class DatasetRead(BaseModel):
    id: str
    knowledge_base_id: str
    name: str
    description: str | None
    case_count: int


class RunRead(BaseModel):
    id: str
    dataset_id: str
    engine: str
    model_name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    correctness_rate: float
    faithfulness_rate: float
    citation_accuracy: float
    median_latency_ms: float
    p95_latency_ms: float


@router.post("/datasets", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
def create_dataset(
    payload: DatasetCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> DatasetRead:
    svc = EvaluationService(session)
    dataset = svc.create_dataset(
        payload.knowledge_base_id, payload.name, payload.description
    )
    return DatasetRead(
        id=dataset.id,
        knowledge_base_id=dataset.knowledge_base_id,
        name=dataset.name,
        description=dataset.description,
        case_count=dataset.case_count,
    )


@router.get("/datasets", response_model=list[DatasetRead])
def list_datasets(
    session: Annotated[Session, Depends(get_db_session)],
) -> list[DatasetRead]:
    datasets = session.scalars(select(EvaluationDataset)).all()
    return [
        DatasetRead(
            id=d.id,
            knowledge_base_id=d.knowledge_base_id,
            name=d.name,
            description=d.description,
            case_count=d.case_count,
        )
        for d in datasets
    ]


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def add_eval_case(
    payload: CaseCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    svc = EvaluationService(session)
    case = svc.add_case(
        dataset_id=payload.dataset_id,
        question=payload.question,
        expected_answer=payload.expected_answer,
        expected_citations=payload.expected_citations,
        language=payload.language,
        is_supported=payload.is_supported,
    )
    return {"id": case.id, "status": "created"}


@router.post("/runs", response_model=RunRead)
async def run_evaluation(
    dataset_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
    generation_queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> RunRead:
    svc = EvaluationService(session)
    rag_svc = RagService(
        session=session,
        settings=settings,
        embedding_provider=embedding_provider,
        generation_provider=generation_provider,
    )
    try:
        slot = await generation_queue.acquire(
            timeout=settings.generation_queue_timeout_seconds
        )
    except TimeoutError as exc:
        raise GenerationQueueFullError(
            "The server is busy with another model request. Please retry shortly."
        ) from exc
    try:
        run = await generation_queue.execute(
            slot,
            lambda: svc.run_evaluation(
                dataset_id,
                rag_svc,
                engine_name=settings.rag_engine,
            ),
            timeout=settings.media_processing_timeout_seconds,
        )
        return RunRead(
            id=run.id,
            dataset_id=run.dataset_id,
            engine=run.engine,
            model_name=run.model_name,
            total_cases=run.total_cases,
            passed_cases=run.passed_cases,
            failed_cases=run.failed_cases,
            correctness_rate=run.correctness_rate,
            faithfulness_rate=run.faithfulness_rate,
            citation_accuracy=run.citation_accuracy,
            median_latency_ms=run.median_latency_ms,
            p95_latency_ms=run.p95_latency_ms,
        )
    except TimeoutError as exc:
        raise GenerationTimeoutError(
            "The evaluation run timed out. Use a smaller dataset and retry."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs", response_model=list[RunRead])
def list_runs(
    session: Annotated[Session, Depends(get_db_session)],
) -> list[RunRead]:
    runs = session.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())).all()
    return [
        RunRead(
            id=r.id,
            dataset_id=r.dataset_id,
            engine=r.engine,
            model_name=r.model_name,
            total_cases=r.total_cases,
            passed_cases=r.passed_cases,
            failed_cases=r.failed_cases,
            correctness_rate=r.correctness_rate,
            faithfulness_rate=r.faithfulness_rate,
            citation_accuracy=r.citation_accuracy,
            median_latency_ms=r.median_latency_ms,
            p95_latency_ms=r.p95_latency_ms,
        )
        for r in runs
    ]
