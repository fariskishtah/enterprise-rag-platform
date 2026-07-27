"""User Feedback routes for collecting rating feedback and analytics."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.services.feedback import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackSubmitRequest(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=36)
    question: str = Field(min_length=2, max_length=4000)
    answer: str = Field(min_length=1, max_length=12000)
    rating: Literal["helpful", "unhelpful"]
    category: str = Field(default="other", min_length=1, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)
    chat_message_id: str | None = Field(default=None, max_length=36)
    engine: str = Field(default="custom", min_length=1, max_length=64)
    model_name: str = Field(default="Qwen", min_length=1, max_length=255)
    latency_ms: float = Field(default=0.0, ge=0.0, le=86_400_000)


class ConvertFeedbackRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=36)


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackSubmitRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    svc = FeedbackService(session)
    entry = svc.submit_feedback(
        knowledge_base_id=payload.knowledge_base_id,
        question=payload.question,
        answer=payload.answer,
        rating=payload.rating,
        category=payload.category,
        comment=payload.comment,
        chat_message_id=payload.chat_message_id,
        engine=payload.engine,
        model_name=payload.model_name,
        latency_ms=payload.latency_ms,
    )
    return {"id": entry.id, "status": "recorded"}


@router.get("/analytics")
def get_feedback_analytics(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    svc = FeedbackService(session)
    return svc.get_analytics()


@router.post("/{feedback_id}/convert-to-eval", status_code=status.HTTP_201_CREATED)
def convert_feedback_to_eval_case(
    feedback_id: str,
    payload: ConvertFeedbackRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    svc = FeedbackService(session)
    case = svc.convert_to_evaluation_case(feedback_id, payload.dataset_id)
    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Feedback entry or Evaluation dataset not found.",
        )
    return {"case_id": case.id, "status": "converted"}
