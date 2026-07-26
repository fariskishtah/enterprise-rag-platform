from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from sqlalchemy.orm import Session

from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.ai.prompting import PROMPT_TEMPLATE_NAME, build_grounded_prompt
from app.ai.vectorstores.base import VectorSearchResult
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.conversation import ChatMessage, ChatRole, ChatSession
from app.repositories.conversations import ConversationRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.rag import (
    CitationRead,
    ClaimSupportStatus,
    RagAnswerRead,
    RagAskRequest,
    RagDebugRead,
    RetrievedSourceRead,
    VerificationRead,
    VerificationStatus,
)
from app.services.answer_processing import (
    NOT_FOUND_ANSWER,
    AnswerPostProcessor,
    supporting_sources,
)
from app.services.query_rewriting import QueryRewriteService
from app.services.reranking import token_set
from app.services.retrieval import RetrievalService
from app.services.verification import VerificationService


def source_to_read(source: VectorSearchResult) -> RetrievedSourceRead:
    return RetrievedSourceRead(
        chunk_id=source.chunk_id,
        document_id=source.document_id,
        document_name=source.document_name,
        text=source.text,
        score=source.score,
        page_number=source.page_number,
        section_index=source.section_index,
        chunk_index=source.chunk_index,
        metadata=source.metadata,
        dense_score=source.dense_score if source.dense_score is not None else source.score,
        lexical_score=source.lexical_score,
        reranking_score=source.reranking_score,
        query_coverage=source.query_coverage,
    )


def source_to_citation(
    source: VectorSearchResult,
    support_text: str | None = None,
) -> CitationRead:
    passage = source.text
    timestamp_start = source.metadata.get("timestamp_start")
    timestamp_end = source.metadata.get("timestamp_end")
    timestamped_segments = source.metadata.get("timestamped_segments")
    if support_text and isinstance(timestamped_segments, list):
        answer_terms = token_set(support_text)
        best_segment: dict[str, object] | None = None
        best_score = -1.0
        for value in timestamped_segments:
            if not isinstance(value, dict) or not isinstance(value.get("text"), str):
                continue
            segment_terms = token_set(value["text"])
            score = len(answer_terms & segment_terms) / max(
                1,
                min(len(answer_terms), len(segment_terms)),
            )
            if score > best_score:
                best_score = score
                best_segment = value
        if best_segment is not None and best_score > 0:
            passage = str(best_segment["text"])
            timestamp_start = best_segment.get("start")
            timestamp_end = best_segment.get("end")
    return CitationRead(
        document_id=source.document_id,
        document_name=source.document_name,
        chunk_id=source.chunk_id,
        passage=passage,
        similarity_score=source.score,
        page_number=source.page_number,
        section_index=source.section_index,
        timestamp_start=timestamp_start,
        timestamp_end=timestamp_end,
        media_source_id=source.metadata.get("media_source_id"),
        support_score=source.score,
    )


class RagService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        generation_provider: GenerationProvider,
    ) -> None:
        self.session = session
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.generation_provider = generation_provider
        self.conversations = ConversationRepository(session)
        self.retrieval = RetrievalService(
            session=session,
            settings=settings,
            embedding_provider=embedding_provider,
        )
        self.rewriter = QueryRewriteService()
        self.verifier = VerificationService()
        self.post_processor = AnswerPostProcessor()

    def ask(self, knowledge_base_id: str, request: RagAskRequest) -> RagAnswerRead:
        started = perf_counter()
        if KnowledgeBaseRepository(self.session).get(knowledge_base_id) is None:
            raise NotFoundError("Knowledge base")
        chat_session = self._resolve_session(
            knowledge_base_id, request.session_id, request.question
        )
        history = self.conversations.recent_messages(
            chat_session.id, self.settings.conversation_history_messages
        )
        rewrite_started = perf_counter()
        rewritten_query = self.rewriter.rewrite(request.question, history)
        rewrite_ms = (perf_counter() - rewrite_started) * 1000
        conversation_context = self._conversation_context(history)

        self.conversations.add_message(
            chat_session=chat_session,
            role=ChatRole.USER,
            content=request.question,
            original_question=request.question,
            rewritten_query=rewritten_query,
        )

        retrieved, retrieval_ms = self.retrieval.retrieve(
            knowledge_base_id=knowledge_base_id,
            query=rewritten_query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            source_document_ids=request.source_document_ids,
        )
        selected = self._bounded_context(retrieved)
        if not selected or not self._has_question_support(selected):
            verification = VerificationRead(
                status=VerificationStatus.UNSUPPORTED,
                claim_support=ClaimSupportStatus.MISSING_ANSWER,
                explanation="No source passage met the configured retrieval threshold.",
                unsupported_statements=[],
            )
            return self._persist_answer(
                chat_session=chat_session,
                request=request,
                rewritten_query=rewritten_query,
                answer=NOT_FOUND_ANSWER,
                direct_answer=NOT_FOUND_ANSWER,
                supporting_explanation="",
                retrieved_sources=selected,
                citation_sources=[],
                verification=verification,
                retrieval_quality="no_results",
                started=started,
                rewrite_ms=rewrite_ms,
                retrieval_ms=retrieval_ms,
                generation_ms=0.0,
                context="",
                not_found=True,
            )

        prompt, context = build_grounded_prompt(
            question=request.question,
            sources=selected,
            conversation_context=conversation_context,
            response_mode=request.response_mode,
            resolved_question=rewritten_query,
        )
        generation_started = perf_counter()
        raw_answer = self.generation_provider.generate(
            prompt,
            temperature=self.settings.generation_temperature,
            max_new_tokens=self.settings.generation_max_new_tokens,
            top_k=self.settings.generation_top_k,
            top_p=self.settings.generation_top_p,
            repetition_penalty=self.settings.generation_repetition_penalty,
            do_sample=self.settings.generation_do_sample,
        )
        generation_ms = (perf_counter() - generation_started) * 1000
        processed = self.post_processor.process(
            question=request.question,
            raw_answer=raw_answer,
            sources=selected,
            response_mode=request.response_mode,
        )
        citation_sources = supporting_sources(
            processed.visible_answer,
            selected,
            processed.cited_chunk_ids,
        )
        not_found = (
            processed.visible_answer == NOT_FOUND_ANSWER
            or self._is_explicit_absence(processed.visible_answer)
            or not citation_sources
            or self._is_excessive_context_copy(processed.visible_answer, citation_sources)
        )
        answer = NOT_FOUND_ANSWER if not_found else processed.visible_answer
        direct_answer = NOT_FOUND_ANSWER if not_found else processed.direct_answer
        supporting_explanation = "" if not_found else processed.supporting_explanation
        if not_found:
            citation_sources = []
        verification = self.verifier.verify(answer, citation_sources)
        quality = self._retrieval_quality(selected, verification)
        return self._persist_answer(
            chat_session=chat_session,
            request=request,
            rewritten_query=rewritten_query,
            answer=answer,
            direct_answer=direct_answer,
            supporting_explanation=supporting_explanation,
            retrieved_sources=selected,
            citation_sources=citation_sources,
            verification=verification,
            retrieval_quality=quality,
            started=started,
            rewrite_ms=rewrite_ms,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            context=context,
            not_found=not_found,
        )

    def _has_question_support(self, sources: list[VectorSearchResult]) -> bool:
        top = sources[0]
        if top.query_coverage >= self.settings.minimum_query_coverage:
            return True
        if top.lexical_score >= 0.2:
            return True
        return (top.dense_score or -1.0) >= 0.55

    @staticmethod
    def _is_excessive_context_copy(answer: str, sources: list[VectorSearchResult]) -> bool:
        normalized = " ".join(answer.lower().split())
        if len(normalized) < 360:
            return False
        return any(normalized in " ".join(source.text.lower().split()) for source in sources)

    @staticmethod
    def _is_explicit_absence(answer: str) -> bool:
        normalized = answer.lower()
        return any(
            phrase in normalized
            for phrase in (
                "does not state",
                "do not state",
                "not specified",
                "not provided",
                "not mentioned",
                "not present",
            )
        )

    def _resolve_session(
        self, knowledge_base_id: str, session_id: str | None, question: str
    ) -> ChatSession:
        if session_id is None:
            return self.conversations.create_session(knowledge_base_id, question.strip()[:80])
        chat_session = self.conversations.get_session(session_id)
        if chat_session is None:
            raise NotFoundError("Chat session")
        if chat_session.knowledge_base_id != knowledge_base_id:
            raise ConflictError(
                code="chat_session_knowledge_base_mismatch",
                message="The chat session belongs to a different knowledge base.",
            )
        return chat_session

    def _bounded_context(self, sources: list[VectorSearchResult]) -> list[VectorSearchResult]:
        selected: list[VectorSearchResult] = []
        remaining = self.settings.max_context_characters
        for source in sources:
            if remaining <= 0:
                break
            if len(source.text) > remaining:
                if not selected:
                    selected.append(replace(source, text=source.text[:remaining]))
                break
            selected.append(source)
            remaining -= len(source.text)
        return selected

    def _conversation_context(self, history: list[ChatMessage]) -> str:
        return "\n".join(
            f"{message.role.value.title()}: {message.content[:1000]}" for message in history
        )

    def _retrieval_quality(
        self,
        sources: list[VectorSearchResult],
        verification: VerificationRead,
    ) -> str:
        top_score = sources[0].score if sources else 0.0
        if top_score >= 0.65 and verification.status is VerificationStatus.SUPPORTED:
            return "high"
        if top_score >= 0.35 and verification.status is not VerificationStatus.UNSUPPORTED:
            return "medium"
        return "low"

    def _persist_answer(
        self,
        *,
        chat_session: ChatSession,
        request: RagAskRequest,
        rewritten_query: str,
        answer: str,
        direct_answer: str,
        supporting_explanation: str,
        retrieved_sources: list[VectorSearchResult],
        citation_sources: list[VectorSearchResult],
        verification: VerificationRead,
        retrieval_quality: str,
        started: float,
        rewrite_ms: float,
        retrieval_ms: float,
        generation_ms: float,
        context: str,
        not_found: bool,
    ) -> RagAnswerRead:
        citations = [source_to_citation(source, answer) for source in citation_sources]
        model_metadata: dict[str, object] = {
            "embedding_model": self.embedding_provider.model_name,
            "generation_model": self.generation_provider.model_name,
            "model_device": str(getattr(self.generation_provider, "device", "local")),
            "retrieval_quality": retrieval_quality,
            "not_found": not_found,
            "support_status": verification.claim_support.value,
        }
        assistant = self.conversations.add_message(
            chat_session=chat_session,
            role=ChatRole.ASSISTANT,
            content=answer,
            original_question=request.question,
            rewritten_query=rewritten_query,
            citations=[citation.model_dump(mode="json") for citation in citations],
            model_metadata=model_metadata,
            verification=verification.model_dump(mode="json"),
        )
        timings = {
            "query_rewrite": round(rewrite_ms, 3),
            "retrieval": round(retrieval_ms, 3),
            "generation": round(generation_ms, 3),
            "total": round((perf_counter() - started) * 1000, 3),
        }
        debug = (
            RagDebugRead(
                original_question=request.question,
                rewritten_query=rewritten_query,
                final_context=context,
                prompt_template=PROMPT_TEMPLATE_NAME,
                embedding_model=self.embedding_provider.model_name,
                generation_model=self.generation_provider.model_name,
                model_device=str(getattr(self.generation_provider, "device", "local")),
                timings_ms=timings,
                retrieval_diagnostics={
                    "strategy": "hybrid_dense_bm25_rerank",
                    "candidate_pool": self.settings.retrieval_candidate_pool,
                    "selected_chunk_ids": [source.chunk_id for source in retrieved_sources],
                    "scores": [
                        {
                            "chunk_id": source.chunk_id,
                            "fused": round(source.score, 4),
                            "dense": round(source.dense_score or 0.0, 4),
                            "lexical": round(source.lexical_score, 4),
                            "rerank": round(source.reranking_score, 4),
                            "query_coverage": round(source.query_coverage, 4),
                        }
                        for source in retrieved_sources
                    ],
                },
            )
            if request.debug
            else None
        )
        return RagAnswerRead(
            session_id=chat_session.id,
            message_id=assistant.id,
            answer=answer,
            direct_answer=direct_answer,
            supporting_explanation=supporting_explanation,
            citations=citations,
            retrieved_sources=[source_to_read(source) for source in retrieved_sources],
            verification=verification,
            retrieval_quality=retrieval_quality,
            confidence=self._confidence(retrieved_sources, verification, not_found),
            support_status=verification.claim_support,
            retrieved_chunk_ids=[source.chunk_id for source in retrieved_sources],
            generation_model=self.generation_provider.model_name,
            model_used=self.generation_provider.model_name,
            response_time=timings["total"],
            response_time_ms=timings["total"],
            not_found=not_found,
            created_at=assistant.created_at,
            debug=debug,
        )

    @staticmethod
    def _confidence(
        sources: list[VectorSearchResult],
        verification: VerificationRead,
        not_found: bool,
    ) -> float:
        if not_found:
            return 0.0
        retrieval = sources[0].score if sources else 0.0
        support_factor = {
            ClaimSupportStatus.FULLY_SUPPORTED: 1.0,
            ClaimSupportStatus.PARTIALLY_SUPPORTED: 0.65,
            ClaimSupportStatus.UNSUPPORTED: 0.2,
            ClaimSupportStatus.CONTRADICTION_DETECTED: 0.0,
            ClaimSupportStatus.MISSING_ANSWER: 0.0,
        }[verification.claim_support]
        return round(max(0.0, min(1.0, retrieval * support_factor)), 4)
