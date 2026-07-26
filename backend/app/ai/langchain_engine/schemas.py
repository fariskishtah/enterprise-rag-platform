from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    source_filename: str
    chunk_id: str
    quote: str
    page: int | None = None
    section: int | None = None


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    not_found: bool = False


class VerificationResult(BaseModel):
    status: Literal["supported", "partially_supported", "unsupported"]
    explanation: str
    unsupported_claims: list[str] = Field(default_factory=list)


class SummaryResult(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    subject: str
    similarities: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class ReportSection(BaseModel):
    heading: str
    content: str
    citations: list[Citation] = Field(default_factory=list)


class ReportResult(BaseModel):
    title: str
    executive_summary: str
    sections: list[ReportSection] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class QueryRewriteResult(BaseModel):
    standalone_query: str
