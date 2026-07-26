from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RuntimeProfile = Literal["low_memory", "balanced", "quality"]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables.

    Production deployments can replace SQLite with any SQLAlchemy-compatible
    relational database URL without changing application code.
    """

    model_config = SettingsConfigDict(
        env_prefix="ENTERPRISE_RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "EnterpriseRAG Pro"
    app_version: str = "0.5.0"
    api_prefix: str = "/api/v1"
    environment: str = "development"
    database_url: str = "sqlite:///./data/enterprise_rag.db"
    storage_path: Path = Path("data/uploads")
    model_cache_path: Path = Path("data/models")
    langchain_index_path: Path = Path("data/langchain_indexes")
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, gt=0)
    max_media_upload_bytes: int = Field(default=500 * 1024 * 1024, gt=0)
    max_media_duration_seconds: int = Field(default=4 * 60 * 60, ge=1)
    media_download_timeout_seconds: int = Field(default=120, ge=5, le=3600)
    media_processing_timeout_seconds: int = Field(default=1800, ge=30, le=7200)
    cors_origins: list[str] = ["http://localhost:5173"]
    chunk_size: int = Field(default=800, ge=128, le=8000)
    chunk_overlap: int = Field(default=120, ge=0, le=2000)
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    generation_model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    generation_fallback_model_name: str = "google/flan-t5-base"
    model_device: str = "auto"
    hf_local_files_only: bool = False
    rag_engine: Literal["custom", "langchain"] = Field(
        default="custom",
        validation_alias=AliasChoices("RAG_ENGINE", "ENTERPRISE_RAG_RAG_ENGINE"),
    )
    generation_quantization: Literal["none", "4bit", "8bit"] = Field(
        default="none",
        validation_alias=AliasChoices(
            "generation_quantization",
            "MODEL_QUANTIZATION",
            "ENTERPRISE_RAG_MODEL_QUANTIZATION",
            "ENTERPRISE_RAG_GENERATION_QUANTIZATION",
        ),
    )
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_candidate_pool: int = Field(default=40, ge=5, le=200)
    similarity_threshold: float = Field(default=0.2, ge=-1.0, le=1.0)
    dense_score_weight: float = Field(default=0.45, ge=0.0, le=1.0)
    lexical_score_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    rerank_score_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    near_duplicate_threshold: float = Field(default=0.88, ge=0.5, le=1.0)
    minimum_query_coverage: float = Field(default=0.16, ge=0.0, le=1.0)
    maximum_sources_per_document: int = Field(default=3, ge=1, le=20)
    generation_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    generation_top_k: int = Field(default=50, ge=0, le=1000)
    generation_top_p: float = Field(default=0.9, gt=0.0, le=1.0)
    generation_max_new_tokens: int = Field(default=256, ge=32, le=2048)
    generation_repetition_penalty: float = Field(default=1.0, ge=1.0, le=5.0)
    generation_do_sample: bool = True
    langchain_parser_retries: int = Field(default=1, ge=0, le=3)
    max_context_characters: int = Field(default=12000, ge=1000, le=100000)
    conversation_history_messages: int = Field(default=6, ge=0, le=20)
    transcription_model_name: str = "small"
    transcription_device: str = "cpu"
    transcription_compute_type: str = "int8"
    transcription_language: str | None = None
    transcription_cpu_threads: int = Field(default=4, ge=1, le=64)

    # ── Runtime profile ──────────────────────────────────────────────────
    runtime_profile: RuntimeProfile = Field(
        default="balanced",
        validation_alias=AliasChoices(
            "APP_RUNTIME_PROFILE",
            "ENTERPRISE_RAG_RUNTIME_PROFILE",
        ),
    )

    # ── Concurrency & timeouts ───────────────────────────────────────────
    max_concurrent_generations: int = Field(default=2, ge=1, le=8)
    generation_timeout_seconds: int = Field(default=90, ge=5, le=600)
    generation_queue_timeout_seconds: int = Field(default=120, ge=5, le=600)
    model_load_timeout_seconds: int = Field(default=120, ge=10, le=600)
    retrieval_timeout_seconds: int = Field(default=30, ge=5, le=120)

    # ── Intelligence operation bounds ────────────────────────────────────
    comparison_max_context_characters: int = Field(default=8000, ge=500, le=100000)
    comparison_timeout_seconds: int = Field(default=120, ge=10, le=600)
    report_timeout_seconds: int = Field(default=180, ge=10, le=900)
    report_section_timeout_seconds: int = Field(default=60, ge=5, le=300)
    summary_timeout_seconds: int = Field(default=60, ge=10, le=300)
    intelligence_max_new_tokens: int = Field(default=256, ge=32, le=2048)

    # ── Verification mode ────────────────────────────────────────────────
    verification_mode: Literal["deterministic", "llm", "skip"] = "deterministic"

    # ── Model lifecycle ──────────────────────────────────────────────────
    model_idle_unload_seconds: int = Field(default=0, ge=0, le=7200)
    langchain_force_wrapper: bool = False

    @field_validator("generation_quantization", mode="before")
    @classmethod
    def normalize_legacy_quantization(cls, value: object) -> object:
        """Keep the previous ``int8`` setting compatible with the course spelling."""

        if isinstance(value, str) and value.lower() == "int8":
            return "8bit"
        return value

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> Settings:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if self.generation_do_sample and self.generation_temperature <= 0:
            raise ValueError(
                "generation_temperature must be greater than zero when sampling is enabled"
            )
        weight_total = (
            self.dense_score_weight + self.lexical_score_weight + self.rerank_score_weight
        )
        if weight_total <= 0:
            raise ValueError("At least one retrieval score weight must be positive")
        return self

    @model_validator(mode="after")
    def apply_profile_defaults(self) -> Settings:
        """Apply sensible defaults based on the selected runtime profile.

        Explicit environment overrides are preserved — this only fills values
        that were left at their class-level defaults.
        """
        if self.runtime_profile == "low_memory":
            _apply_if_default(self, "max_concurrent_generations", 1, 2)
            _apply_if_default(self, "generation_max_new_tokens", 128, 256)
            _apply_if_default(self, "max_context_characters", 4000, 12000)
            _apply_if_default(self, "retrieval_top_k", 3, 5)
            _apply_if_default(self, "retrieval_candidate_pool", 20, 40)
            _apply_if_default(self, "generation_timeout_seconds", 45, 90)
            _apply_if_default(self, "generation_queue_timeout_seconds", 60, 120)
            _apply_if_default(self, "comparison_max_context_characters", 3000, 8000)
            _apply_if_default(self, "comparison_timeout_seconds", 90, 120)
            _apply_if_default(self, "report_timeout_seconds", 120, 180)
            _apply_if_default(self, "report_section_timeout_seconds", 45, 60)
            _apply_if_default(self, "summary_timeout_seconds", 45, 60)
            _apply_if_default(self, "intelligence_max_new_tokens", 160, 256)
            _apply_if_default(self, "langchain_parser_retries", 0, 1)
            _apply_if_default(self, "langchain_force_wrapper", True, False)
            _apply_if_default(self, "conversation_history_messages", 4, 6)
        elif self.runtime_profile == "quality":
            _apply_if_default(self, "max_concurrent_generations", 4, 2)
            _apply_if_default(self, "generation_max_new_tokens", 512, 256)
            _apply_if_default(self, "intelligence_max_new_tokens", 512, 256)
        return self


def _apply_if_default(
    settings: Settings, field: str, profile_value: object, default: object
) -> None:
    """Set *field* to *profile_value* only when the current value matches the
    class-level *default*, indicating no explicit user override."""
    if getattr(settings, field) == default:
        object.__setattr__(settings, field, profile_value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
