from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.rag import CitationRead, VerificationRead


class SummaryKind(StrEnum):
    WHOLE_DOCUMENT = "whole_document"
    KNOWLEDGE_BASE = "knowledge_base"
    SECTION = "section"
    KEY_POINTS = "key_points"
    EXECUTIVE = "executive_summary"


class SummaryRequest(BaseModel):
    knowledge_base_id: str
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    kind: SummaryKind
    section_index: int | None = Field(default=None, ge=0)
    output_language: Literal["auto", "ar", "en"] = "auto"


class SummaryRead(BaseModel):
    kind: SummaryKind
    content: str
    citations: list[CitationRead]
    verification: VerificationRead
    model_used: str
    output_language: Literal["ar", "en"]


class ComparisonRequest(BaseModel):
    knowledge_base_id: str
    document_ids: list[str] = Field(min_length=2, max_length=10)
    output_language: Literal["auto", "ar", "en"] = "auto"

    @model_validator(mode="after")
    def require_unique_documents(self) -> "ComparisonRequest":
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must be unique")
        return self


class ComparisonRead(BaseModel):
    common_themes: str
    differences: str
    contradictions: str
    methodologies: str
    conclusions: str
    limitations: str
    citations: list[CitationRead]
    verification: VerificationRead
    model_used: str
    elapsed_ms: float | None = None
    generation_calls: int | None = None
    partial: bool = False
    output_language: Literal["ar", "en"]


class ReportRequest(BaseModel):
    knowledge_base_id: str
    document_ids: list[str] = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=2, max_length=2000)
    output_language: Literal["auto", "ar", "en"] = "auto"


class ResearchReportRead(BaseModel):
    title: str
    objective: str
    executive_summary: str
    findings: str
    comparison: str
    risks_and_limitations: str
    conclusions: str
    cited_sources: list[CitationRead]
    verification: VerificationRead
    markdown: str
    model_used: str
    elapsed_ms: float | None = None
    generation_calls: int | None = None
    partial: bool = False
    output_language: Literal["ar", "en"]
