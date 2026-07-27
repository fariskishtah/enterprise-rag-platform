"""Evaluation service for executing benchmark test runs and metrics analytics."""

from __future__ import annotations

import logging
import re
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.evaluation import (
    MAX_EVALUATION_CASES_PER_DATASET,
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
)
from app.schemas.rag import RagAskRequest
from app.services.rag import RagService

logger = logging.getLogger(__name__)


def _answer_coverage(expected: str, actual: str) -> float:
    expected_terms = set(re.findall(r"\w+", expected.casefold()))
    if not expected_terms:
        return 1.0
    actual_terms = set(re.findall(r"\w+", actual.casefold()))
    return len(expected_terms & actual_terms) / len(expected_terms)


class EvaluationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_dataset(
        self, knowledge_base_id: str, name: str, description: str | None = None
    ) -> EvaluationDataset:
        dataset = EvaluationDataset(
            knowledge_base_id=knowledge_base_id,
            name=name,
            description=description,
            case_count=0,
        )
        self.session.add(dataset)
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def add_case(
        self,
        dataset_id: str,
        question: str,
        expected_answer: str | None = None,
        expected_citations: list[str] | None = None,
        language: str = "en",
        is_supported: bool = True,
    ) -> EvaluationCase:
        dataset = self.session.scalar(
            select(EvaluationDataset).where(EvaluationDataset.id == dataset_id)
        )
        if dataset is None:
            raise ValueError("Evaluation dataset not found")
        if dataset.case_count >= MAX_EVALUATION_CASES_PER_DATASET:
            raise AppError(
                status_code=422,
                code="evaluation_case_quota_exceeded",
                message=(
                    "This evaluation dataset has reached the public-demo case limit. "
                    "Create a smaller dataset or remove cases before adding more."
                ),
            )

        case = EvaluationCase(
            dataset_id=dataset_id,
            question=question,
            expected_answer=expected_answer,
            expected_citations=expected_citations or [],
            language=language,
            is_supported=is_supported,
        )
        self.session.add(case)
        dataset.case_count += 1
        self.session.commit()
        self.session.refresh(case)
        return case

    def run_evaluation(
        self, dataset_id: str, rag_service: RagService, engine_name: str = "custom"
    ) -> EvaluationRun:
        dataset = self.session.scalar(
            select(EvaluationDataset).where(EvaluationDataset.id == dataset_id)
        )
        if dataset is None or not dataset.cases:
            raise ValueError("Evaluation dataset has no test cases")
        if len(dataset.cases) > MAX_EVALUATION_CASES_PER_DATASET:
            raise AppError(
                status_code=422,
                code="evaluation_case_quota_exceeded",
                message="The evaluation dataset exceeds the public-demo case limit.",
            )

        run = EvaluationRun(
            dataset_id=dataset_id,
            engine=engine_name,
            model_name=rag_service.generation_provider.model_name,
            total_cases=len(dataset.cases),
            passed_cases=0,
            failed_cases=0,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        passed_count = 0
        latencies: list[float] = []
        faithfulness_scores: list[float] = []
        citation_scores: list[float] = []

        for case in dataset.cases:
            started = perf_counter()
            try:
                answer = rag_service.ask(
                    dataset.knowledge_base_id, RagAskRequest(question=case.question)
                )
                elapsed_ms = (perf_counter() - started) * 1000
                latencies.append(elapsed_ms)

                is_passed = answer.not_found == (not case.is_supported)
                if case.is_supported and case.expected_answer:
                    is_passed = is_passed and _answer_coverage(
                        case.expected_answer,
                        answer.answer,
                    ) >= 0.5

                returned_citations = {value.chunk_id for value in answer.citations}
                expected_citations = set(case.expected_citations)
                if expected_citations:
                    citation_score = len(
                        expected_citations & returned_citations
                    ) / len(expected_citations)
                    is_passed = is_passed and citation_score == 1.0
                elif case.is_supported:
                    citation_score = 1.0 if returned_citations else 0.0
                else:
                    citation_score = 1.0 if not returned_citations else 0.0
                citation_scores.append(citation_score)

                verification_status = str(answer.verification.status)
                if (
                    not case.is_supported and answer.not_found
                ) or verification_status == "supported":
                    faithfulness_scores.append(1.0)
                elif verification_status == "partially_supported":
                    faithfulness_scores.append(0.5)
                else:
                    faithfulness_scores.append(0.0)

                if is_passed:
                    passed_count += 1

                res = EvaluationResult(
                    run_id=run.id,
                    case_id=case.id,
                    passed=is_passed,
                    generated_answer=answer.answer,
                    verification_status=str(answer.verification.status),
                    returned_citations=sorted(returned_citations),
                    latency_ms=elapsed_ms,
                )
                self.session.add(res)
            except Exception:
                elapsed_ms = (perf_counter() - started) * 1000
                faithfulness_scores.append(0.0)
                citation_scores.append(0.0)
                res = EvaluationResult(
                    run_id=run.id,
                    case_id=case.id,
                    passed=False,
                    generated_answer="",
                    verification_status="error",
                    returned_citations=[],
                    latency_ms=elapsed_ms,
                    error_message="Evaluation case failed.",
                )
                self.session.add(res)

        latencies.sort()
        med_lat = latencies[len(latencies) // 2] if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95_lat = latencies[p95_idx] if latencies else 0.0

        run.passed_cases = passed_count
        run.failed_cases = len(dataset.cases) - passed_count
        run.correctness_rate = round(passed_count / len(dataset.cases), 2)
        run.faithfulness_rate = round(
            sum(faithfulness_scores) / len(dataset.cases), 2
        )
        run.citation_accuracy = round(
            sum(citation_scores) / len(dataset.cases), 2
        )
        run.median_latency_ms = round(med_lat, 1)
        run.p95_latency_ms = round(p95_lat, 1)

        self.session.commit()
        self.session.refresh(run)
        return run
