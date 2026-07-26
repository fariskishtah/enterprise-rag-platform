from __future__ import annotations

from time import perf_counter

from langchain_core.documents import Document as LangChainDocument
from langchain_core.exceptions import OutputParserException
from sqlalchemy.orm import Session

from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.ai.langchain_engine.chains import CourseChainSuite, format_documents
from app.ai.langchain_engine.document_pipeline import EmbeddingModelMismatchError
from app.ai.langchain_engine.runtime import LangChainEngineRuntime
from app.ai.langchain_engine.schemas import GroundedAnswer, QueryRewriteResult, VerificationResult
from app.ai.vectorstores.base import VectorSearchResult
from app.core.config import Settings
from app.core.errors import ConflictError, ModelProviderError, NotFoundError
from app.models.conversation import ChatRole
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.rag import (
    ClaimSupportStatus,
    RagAnswerRead,
    RagAskRequest,
    VerificationRead,
    VerificationStatus,
)
from app.services.language import not_found_answer, resolve_output_language
from app.services.rag import RagService


class LangChainRagService(RagService):
    """FastAPI-compatible RAG service backed by persistent FAISS and composed LCEL."""

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        generation_provider: GenerationProvider,
        runtime: LangChainEngineRuntime,
    ) -> None:
        super().__init__(
            session=session,
            settings=settings,
            embedding_provider=embedding_provider,
            generation_provider=generation_provider,
        )
        self.runtime = runtime

    def ask(self, knowledge_base_id: str, request: RagAskRequest) -> RagAnswerRead:
        started = perf_counter()
        output_language = resolve_output_language(request.output_language, request.question)
        if KnowledgeBaseRepository(self.session).get(knowledge_base_id) is None:
            raise NotFoundError("Knowledge base")
        chat_session = self._resolve_session(
            knowledge_base_id,
            request.session_id,
            request.question,
        )
        history = self.conversations.recent_messages(
            chat_session.id,
            self.settings.conversation_history_messages,
        )
        conversation_context = self._conversation_context(history)
        self.conversations.add_message(
            chat_session=chat_session,
            role=ChatRole.USER,
            content=request.question,
            original_question=request.question,
        )

        try:
            retriever = self.runtime.document_pipeline.retriever(
                knowledge_base_id,
                top_k=request.top_k or self.settings.retrieval_top_k,
                document_ids=request.source_document_ids,
            )
        except FileNotFoundError:
            return self._not_found(
                chat_session=chat_session,
                request=request,
                started=started,
                explanation="No persisted LangChain FAISS index exists for this knowledge base.",
            )
        except EmbeddingModelMismatchError as exc:
            raise ConflictError(
                code="embedding_model_reindex_required",
                message=(
                    "The embedding model changed. Reindex this knowledge base before searching."
                ),
            ) from exc

        suite = CourseChainSuite(
            llm=self.runtime.llm,
            retriever=retriever,
            parser_retries=self.settings.langchain_parser_retries,
        )
        generation_started = perf_counter()
        try:
            state = suite.invoke(
                question=request.question,
                conversation_history=conversation_context,
                answer_language_instruction=(
                    "Answer in Arabic. Preserve names, dates, and numbers exactly."
                    if output_language == "ar"
                    else "Answer in English. Preserve names, dates, and numbers exactly."
                ),
            )
        except OutputParserException as exc:
            raise ModelProviderError(
                "The LangChain model did not return valid structured output after repair."
            ) from exc
        generation_ms = (perf_counter() - generation_started) * 1000

        rewrite: QueryRewriteResult = state["rewrite"]
        documents: list[LangChainDocument] = state["documents"]
        parsed_answer: GroundedAnswer = state["answer"]
        parsed_verification: VerificationResult = state["verification"]
        sources = self._vector_results(documents)
        citations = self._citation_sources(parsed_answer, sources)
        not_found = parsed_answer.not_found or not parsed_answer.answer.strip() or not citations
        answer = not_found_answer(output_language) if not_found else parsed_answer.answer.strip()
        verification = self._verification_read(parsed_verification, not_found=not_found)

        result = self._persist_answer(
            chat_session=chat_session,
            request=request,
            rewritten_query=rewrite.standalone_query,
            answer=answer,
            direct_answer=answer,
            supporting_explanation="",
            retrieved_sources=sources,
            citation_sources=[] if not_found else citations,
            verification=verification,
            retrieval_quality=self._retrieval_quality(sources, verification),
            started=started,
            rewrite_ms=0.0,
            retrieval_ms=0.0,
            generation_ms=generation_ms,
            context=format_documents(documents),
            not_found=not_found,
        )
        if result.debug is not None:
            result.debug.prompt_template = "langchain-grounded-qa-v1"
            result.debug.retrieval_diagnostics = {
                "strategy": "langchain_faiss_similarity",
                "engine": "langchain",
                "llm_backend": self.runtime.llm_backend,
                "llm_fallback_reason": self.runtime.llm_fallback_reason,
                "selected_chunk_ids": [source.chunk_id for source in sources],
            }
        return result

    def _not_found(
        self,
        *,
        chat_session: object,
        request: RagAskRequest,
        started: float,
        explanation: str,
    ) -> RagAnswerRead:
        verification = VerificationRead(
            status=VerificationStatus.UNSUPPORTED,
            claim_support=ClaimSupportStatus.MISSING_ANSWER,
            explanation=explanation,
            unsupported_statements=[],
        )
        return self._persist_answer(
            chat_session=chat_session,
            request=request,
            rewritten_query=request.question,
            answer=not_found_answer(
                resolve_output_language(request.output_language, request.question)
            ),
            direct_answer=not_found_answer(
                resolve_output_language(request.output_language, request.question)
            ),
            supporting_explanation="",
            retrieved_sources=[],
            citation_sources=[],
            verification=verification,
            retrieval_quality="no_results",
            started=started,
            rewrite_ms=0.0,
            retrieval_ms=0.0,
            generation_ms=0.0,
            context="",
            not_found=True,
        )

    @staticmethod
    def _vector_results(documents: list[LangChainDocument]) -> list[VectorSearchResult]:
        total = max(1, len(documents))
        results: list[VectorSearchResult] = []
        for rank, document in enumerate(documents):
            metadata = document.metadata
            score = max(0.0, 1.0 - rank / total)
            results.append(
                VectorSearchResult(
                    chunk_id=str(metadata.get("chunk_id", f"langchain-{rank}")),
                    document_id=str(metadata.get("document_id", "")),
                    document_name=str(metadata.get("source_filename", "source")),
                    text=document.page_content,
                    score=score,
                    page_number=metadata.get("page"),
                    section_index=metadata.get("section"),
                    chunk_index=int(metadata.get("chunk_index", rank)),
                    metadata=dict(metadata),
                    dense_score=score,
                    query_coverage=score,
                )
            )
        return results

    @staticmethod
    def _citation_sources(
        answer: GroundedAnswer,
        sources: list[VectorSearchResult],
    ) -> list[VectorSearchResult]:
        requested_ids = {citation.chunk_id for citation in answer.citations}
        selected = [source for source in sources if source.chunk_id in requested_ids]
        return selected or ([] if answer.not_found else sources[:2])

    @staticmethod
    def _verification_read(
        result: VerificationResult,
        *,
        not_found: bool,
    ) -> VerificationRead:
        if not_found:
            return VerificationRead(
                status=VerificationStatus.UNSUPPORTED,
                claim_support=ClaimSupportStatus.MISSING_ANSWER,
                explanation=result.explanation,
                unsupported_statements=result.unsupported_claims,
            )
        status_map = {
            "supported": (
                VerificationStatus.SUPPORTED,
                ClaimSupportStatus.FULLY_SUPPORTED,
            ),
            "partially_supported": (
                VerificationStatus.PARTIALLY_SUPPORTED,
                ClaimSupportStatus.PARTIALLY_SUPPORTED,
            ),
            "unsupported": (
                VerificationStatus.UNSUPPORTED,
                ClaimSupportStatus.UNSUPPORTED,
            ),
        }
        status, support = status_map[result.status]
        return VerificationRead(
            status=status,
            claim_support=support,
            explanation=result.explanation,
            unsupported_statements=result.unsupported_claims,
        )
