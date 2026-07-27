"""User Feedback service for recording user rating feedback and analytics."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.evaluation import (
    MAX_EVALUATION_CASES_PER_DATASET,
    EvaluationCase,
    EvaluationDataset,
)
from app.models.feedback import UserFeedback

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def submit_feedback(
        self,
        *,
        knowledge_base_id: str,
        question: str,
        answer: str,
        rating: str,
        category: str = "other",
        comment: str | None = None,
        chat_message_id: str | None = None,
        engine: str = "custom",
        model_name: str = "Qwen",
        latency_ms: float = 0.0,
    ) -> UserFeedback:
        feedback = UserFeedback(
            knowledge_base_id=knowledge_base_id,
            chat_message_id=chat_message_id,
            question=question,
            answer=answer,
            rating=rating,
            category=category,
            comment=comment,
            engine=engine,
            model_name=model_name,
            latency_ms=latency_ms,
        )
        self.session.add(feedback)
        self.session.commit()
        self.session.refresh(feedback)
        return feedback

    def get_analytics(self) -> dict[str, Any]:
        total = self.session.scalar(select(func.count(UserFeedback.id))) or 0
        helpful = (
            self.session.scalar(
                select(func.count(UserFeedback.id)).where(UserFeedback.rating == "helpful")
            )
            or 0
        )
        unhelpful = total - helpful

        helpful_rate = round(helpful / total, 2) if total > 0 else 0.0

        # Complaint categories count
        categories_query = (
            select(UserFeedback.category, func.count(UserFeedback.id))
            .where(UserFeedback.rating == "unhelpful")
            .group_by(UserFeedback.category)
        )
        complaint_counts = dict(self.session.execute(categories_query).all())

        return {
            "total_feedback": total,
            "helpful_count": helpful,
            "unhelpful_count": unhelpful,
            "helpful_rate": helpful_rate,
            "complaint_categories": complaint_counts,
        }

    def convert_to_evaluation_case(
        self, feedback_id: str, dataset_id: str
    ) -> EvaluationCase | None:
        feedback = self.session.scalar(select(UserFeedback).where(UserFeedback.id == feedback_id))
        dataset = self.session.scalar(
            select(EvaluationDataset).where(EvaluationDataset.id == dataset_id)
        )
        if feedback is None or dataset is None:
            return None
        if dataset.case_count >= MAX_EVALUATION_CASES_PER_DATASET:
            raise AppError(
                status_code=422,
                code="evaluation_case_quota_exceeded",
                message="This evaluation dataset has reached the public-demo case limit.",
            )

        case = EvaluationCase(
            dataset_id=dataset_id,
            question=feedback.question,
            expected_answer=feedback.comment or feedback.answer,
            language="en",
            is_supported=True,
        )
        self.session.add(case)
        dataset.case_count += 1
        feedback.converted_to_eval_case_id = case.id
        self.session.commit()
        self.session.refresh(case)
        return case
