from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.vectorstores.base import VectorSearchResult, VectorStore
from app.models.document import Document, DocumentChunk


class RelationalVectorStore(VectorStore):
    """Persistent dense-vector adapter backed by the relational chunk table.

    Vectors are stored as float32 binary values. Similarity is calculated in-process for
    the local deployment profile, while the interface permits FAISS, pgvector, or Chroma
    adapters later without changing processing or RAG services.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        chunks: list[DocumentChunk],
        embeddings: np.ndarray,
        *,
        model_name: str,
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match.")
        indexed_at = datetime.now(UTC)
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            vector = np.asarray(embedding, dtype=np.float32)
            if vector.ndim != 1 or vector.size == 0:
                raise ValueError("Every embedding must be a non-empty one-dimensional vector.")
            chunk.embedding = vector.tobytes()
            chunk.embedding_dimension = int(vector.size)
            chunk.embedding_model = model_name
            chunk.indexed_at = indexed_at
            self.session.add(chunk)
        self.session.flush()
        return len(chunks)

    def search(
        self,
        *,
        knowledge_base_id: str,
        query_embedding: np.ndarray,
        top_k: int,
        similarity_threshold: float,
    ) -> list[VectorSearchResult]:
        statement = (
            select(DocumentChunk, Document.name)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.knowledge_base_id == knowledge_base_id,
                DocumentChunk.embedding.is_not(None),
                DocumentChunk.indexed_at.is_not(None),
            )
        )
        rows = self.session.execute(statement).all()
        query = np.asarray(query_embedding, dtype=np.float32)
        query_norm = float(np.linalg.norm(query))
        if query.ndim != 1 or query.size == 0 or query_norm == 0:
            return []
        query = query / query_norm

        results: list[VectorSearchResult] = []
        for chunk, document_name in rows:
            vector = np.frombuffer(chunk.embedding, dtype=np.float32)
            if vector.size != query.size:
                continue
            vector_norm = float(np.linalg.norm(vector))
            if vector_norm == 0:
                continue
            score = float(np.dot(query, vector / vector_norm))
            if score < similarity_threshold:
                continue
            results.append(
                VectorSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=document_name,
                    text=chunk.text,
                    score=score,
                    page_number=chunk.page_number,
                    section_index=chunk.section_index,
                    chunk_index=chunk.chunk_index,
                    metadata=chunk.extraction_metadata,
                )
            )
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results[:top_k]

    def delete_document(self, document_id: str) -> None:
        self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        self.session.flush()
