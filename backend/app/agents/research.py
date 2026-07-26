from dataclasses import dataclass

from app.ai.vectorstores.base import VectorSearchResult
from app.services.retrieval import RetrievalService


@dataclass(frozen=True)
class ResearchAgentInput:
    knowledge_base_id: str
    query: str
    top_k: int | None = None


class ResearchAgent:
    """Retrieves evidence; it never generates or mutates source content."""

    def __init__(self, retrieval: RetrievalService) -> None:
        self.retrieval = retrieval

    def run(self, request: ResearchAgentInput) -> list[VectorSearchResult]:
        results, _ = self.retrieval.retrieve(
            knowledge_base_id=request.knowledge_base_id,
            query=request.query,
            top_k=request.top_k,
        )
        return results
