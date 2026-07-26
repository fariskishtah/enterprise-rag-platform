import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.generation_queue import GenerationQueue
from app.ai.interfaces import GenerationProvider
from app.api.dependencies import (
    get_db_session,
    get_generation_provider,
    get_generation_queue,
    get_runtime_settings,
)
from app.core.config import Settings
from app.core.errors import GenerationTimeoutError
from app.schemas.intelligence import (
    ComparisonRead,
    ComparisonRequest,
    ReportRequest,
    ResearchReportRead,
    SummaryRead,
    SummaryRequest,
)
from app.services.intelligence import (
    ComparisonService,
    ReportService,
    SummaryService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.post("/summaries", response_model=SummaryRead)
async def create_summary(
    payload: SummaryRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
    generation_queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> SummaryRead:
    try:
        q_timeout = settings.generation_queue_timeout_seconds
        async with await generation_queue.acquire(timeout=q_timeout):
            return await asyncio.wait_for(
                asyncio.to_thread(
                    _run_summary, session, settings, generation_provider, payload
                ),
                timeout=settings.summary_timeout_seconds,
            )
    except TimeoutError as exc:
        raise GenerationTimeoutError(
            "Summary generation timed out. Try a shorter document or fewer sources."
        ) from exc


@router.post("/comparisons", response_model=ComparisonRead)
async def compare_documents(
    payload: ComparisonRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
    generation_queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> ComparisonRead:
    try:
        q_timeout = settings.generation_queue_timeout_seconds
        async with await generation_queue.acquire(timeout=q_timeout):
            return await asyncio.wait_for(
                asyncio.to_thread(
                    _run_comparison, session, settings, generation_provider, payload
                ),
                timeout=settings.comparison_timeout_seconds,
            )
    except TimeoutError as exc:
        raise GenerationTimeoutError(
            "Comparison timed out. Try comparing fewer documents or narrower topics."
        ) from exc


@router.post("/reports", response_model=ResearchReportRead)
async def create_report(
    payload: ReportRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    generation_provider: Annotated[GenerationProvider, Depends(get_generation_provider)],
    generation_queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
) -> ResearchReportRead:
    try:
        q_timeout = settings.generation_queue_timeout_seconds
        async with await generation_queue.acquire(timeout=q_timeout):
            return await asyncio.wait_for(
                asyncio.to_thread(
                    _run_report, session, settings, generation_provider, payload
                ),
                timeout=settings.report_timeout_seconds,
            )
    except TimeoutError as exc:
        raise GenerationTimeoutError(
            "Report generation timed out. Try a narrower objective or fewer source documents."
        ) from exc


# ── Synchronous service runners (executed via asyncio.to_thread) ─────


def _run_summary(
    session: Session,
    settings: Settings,
    generation_provider: GenerationProvider,
    payload: SummaryRequest,
) -> SummaryRead:
    return SummaryService(
        session=session,
        settings=settings,
        generation_provider=generation_provider,
    ).generate(payload)


def _run_comparison(
    session: Session,
    settings: Settings,
    generation_provider: GenerationProvider,
    payload: ComparisonRequest,
) -> ComparisonRead:
    return ComparisonService(
        session=session,
        settings=settings,
        generation_provider=generation_provider,
    ).compare(payload)


def _run_report(
    session: Session,
    settings: Settings,
    generation_provider: GenerationProvider,
    payload: ReportRequest,
) -> ResearchReportRead:
    return ReportService(
        session=session,
        settings=settings,
        generation_provider=generation_provider,
    ).create(payload)
