from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.models.document import DocumentChunk


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    page_number: int | None
    section_index: int | None
    chunk_index: int
    metadata: dict[str, Any]
    dense_score: float | None = None
    lexical_score: float = 0.0
    reranking_score: float = 0.0
    query_coverage: float = 0.0


class VectorStore(ABC):
    @abstractmethod
    def upsert(
        self,
        chunks: list[DocumentChunk],
        embeddings: np.ndarray,
        *,
        model_name: str,
    ) -> int: ...

    @abstractmethod
    def search(
        self,
        *,
        knowledge_base_id: str,
        query_embedding: np.ndarray,
        model_name: str,
        top_k: int,
        similarity_threshold: float,
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...
