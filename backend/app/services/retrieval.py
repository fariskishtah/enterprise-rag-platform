from __future__ import annotations

from time import perf_counter

from sqlalchemy.orm import Session

from app.ai.interfaces import EmbeddingProvider
from app.ai.vectorstores.base import VectorSearchResult
from app.ai.vectorstores.relational import RelationalVectorStore
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.services.reranking import HybridReranker


class RetrievalService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.session = session
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.vector_store = RelationalVectorStore(session)

    def retrieve(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        source_document_ids: list[str] | None = None,
    ) -> tuple[list[VectorSearchResult], float]:
        if KnowledgeBaseRepository(self.session).get(knowledge_base_id) is None:
            raise NotFoundError("Knowledge base")
        started = perf_counter()
        query_embedding = self.embedding_provider.embed_query(query)
        requested_top_k = top_k or self.settings.retrieval_top_k
        candidate_pool = max(self.settings.retrieval_candidate_pool, requested_top_k * 8)
        candidates = self.vector_store.search(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=candidate_pool,
            similarity_threshold=-1.0,
        )
        if source_document_ids:
            allowed = set(source_document_ids)
            candidates = [item for item in candidates if item.document_id in allowed]
        threshold = (
            self.settings.similarity_threshold
            if similarity_threshold is None
            else similarity_threshold
        )
        candidates = [item for item in candidates if item.score >= threshold]
        results = HybridReranker(self.settings).rerank(
            query=query,
            candidates=candidates,
            top_k=requested_top_k,
        )
        return results, (perf_counter() - started) * 1000
