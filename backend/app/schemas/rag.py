from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class VerificationStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"


class ClaimSupportStatus(StrEnum):
    FULLY_SUPPORTED = "fully_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTION_DETECTED = "contradiction_detected"
    MISSING_ANSWER = "missing_answer"


class RetrievedSourceRead(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    page_number: int | None
    section_index: int | None
    chunk_index: int
    metadata: dict[str, Any]
    dense_score: float
    lexical_score: float
    reranking_score: float
    query_coverage: float


class CitationRead(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    passage: str
    similarity_score: float
    page_number: int | None
    section_index: int | None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    media_source_id: str | None = None
    support_score: float = 0.0


class VerificationRead(BaseModel):
    status: VerificationStatus
    claim_support: ClaimSupportStatus = ClaimSupportStatus.UNSUPPORTED
    explanation: str
    unsupported_statements: list[str]
    supported_statements: list[str] = Field(default_factory=list)
    contradiction_detected: bool = False
    claim_scores: dict[str, float] = Field(default_factory=dict)


class RagAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    session_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=-1.0, le=1.0)
    response_mode: str = Field(default="concise", pattern="^(concise|detailed)$")
    output_language: Literal["auto", "ar", "en"] = "auto"
    source_document_ids: list[str] = Field(default_factory=list, max_length=50)
    debug: bool = False


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=-1.0, le=1.0)
    source_document_ids: list[str] = Field(default_factory=list, max_length=50)


class RetrievalResponse(BaseModel):
    query: str
    sources: list[RetrievedSourceRead]
    embedding_model: str
    elapsed_ms: float


class RagDebugRead(BaseModel):
    original_question: str
    rewritten_query: str
    final_context: str
    prompt_template: str
    embedding_model: str
    generation_model: str
    model_device: str
    timings_ms: dict[str, float]
    retrieval_diagnostics: dict[str, Any] = Field(default_factory=dict)


class RagAnswerRead(BaseModel):
    session_id: str
    message_id: str
    answer: str
    direct_answer: str
    supporting_explanation: str
    citations: list[CitationRead]
    retrieved_sources: list[RetrievedSourceRead]
    verification: VerificationRead
    retrieval_quality: str
    confidence: float
    support_status: ClaimSupportStatus
    retrieved_chunk_ids: list[str]
    generation_model: str
    model_used: str
    response_time: float
    response_time_ms: float
    not_found: bool
    output_language: Literal["ar", "en"]
    created_at: datetime
    debug: RagDebugRead | None = None


class RagConfigurationRead(BaseModel):
    embedding_model: str
    generation_model: str
    rag_engine: str
    quantization: str
    model_device: str
    embedding_model_cached: bool
    generation_model_cached: bool
    model_warm: bool
    embedding_model_status: Literal["cold", "loading", "ready", "busy", "failed"] = "cold"
    generation_model_status: Literal["cold", "loading", "ready", "busy", "failed"] = "cold"
    warmup_status: Literal["cold", "loading", "ready", "busy", "failed"] = "cold"
    vector_store: str
    top_k: int
    candidate_pool: int
    similarity_threshold: float
    retrieval_strategy: str
    score_weights: dict[str, float]
    chunk_size: int
    chunk_overlap: int
    temperature: float
    generation_top_k: int
    top_p: float
    maximum_new_tokens: int
    repetition_penalty: float
    do_sample: bool
    maximum_context_characters: int
    conversation_history_messages: int
    runtime_profile: str = "balanced"
    generation_queue_active: int = 0
    generation_queue_queued: int = 0
    generation_timeout_seconds: int = 90
    embedding_reindex_required: bool = False
    maximum_upload_mb: int = 50
    maximum_document_pages: int = 300
    maximum_media_duration_minutes: int = 30
    maximum_files_per_knowledge_base: int = 25
    maximum_knowledge_bases: int = 5
    maximum_concurrent_heavy_operations: int = 1
    heavy_queue_max_size: int = 2
    demo_data_retention_hours: int = 24
