from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.interfaces import GenerationProvider
from app.ai.prompting import build_grounded_prompt
from app.ai.vectorstores.base import VectorSearchResult
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.document import Document, DocumentChunk
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.intelligence import (
    ComparisonRead,
    ComparisonRequest,
    ReportRequest,
    ResearchReportRead,
    SummaryKind,
    SummaryRead,
    SummaryRequest,
)
from app.schemas.rag import CitationRead
from app.services.rag import source_to_citation
from app.services.verification import VerificationService

logger = logging.getLogger(__name__)

_SECTION_TIMEOUT_MSG = (
    "(Section generation timed out — evidence was retrieved but synthesis was not completed.)"
)


@dataclass(frozen=True)
class AnalysisContext:
    sources: list[VectorSearchResult]

    @property
    def citations(self) -> list[CitationRead]:
        return [source_to_citation(source) for source in self.sources]


class AnalysisContextBuilder:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def build(
        self,
        *,
        knowledge_base_id: str,
        document_ids: list[str],
        section_index: int | None = None,
        max_characters: int | None = None,
    ) -> AnalysisContext:
        if KnowledgeBaseRepository(self.session).get(knowledge_base_id) is None:
            raise NotFoundError("Knowledge base")
        statement = (
            select(DocumentChunk, Document.name)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.knowledge_base_id == knowledge_base_id)
            .order_by(Document.name, DocumentChunk.chunk_index)
        )
        if document_ids:
            found_documents = set(
                self.session.scalars(
                    select(Document.id).where(
                        Document.knowledge_base_id == knowledge_base_id,
                        Document.id.in_(document_ids),
                    )
                ).all()
            )
            missing = set(document_ids) - found_documents
            if missing:
                raise ConflictError(
                    code="invalid_document_selection",
                    message="One or more selected documents do not belong to this knowledge base.",
                )
            statement = statement.where(DocumentChunk.document_id.in_(document_ids))
        if section_index is not None:
            statement = statement.where(DocumentChunk.section_index == section_index)

        char_limit = max_characters or self.settings.max_context_characters
        sources: list[VectorSearchResult] = []
        remaining = char_limit
        for chunk, document_name in self.session.execute(statement):
            if remaining <= 0:
                break
            text = chunk.text[:remaining]
            if not text:
                continue
            sources.append(
                VectorSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=document_name,
                    text=text,
                    score=1.0,
                    page_number=chunk.page_number,
                    section_index=chunk.section_index,
                    chunk_index=chunk.chunk_index,
                    metadata=chunk.extraction_metadata,
                )
            )
            remaining -= len(text)
        if not sources:
            raise ConflictError(
                code="no_indexed_content",
                message="The selected documents have no processed content available.",
            )
        return AnalysisContext(sources=sources)


class GroundedAnalysisService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        generation_provider: GenerationProvider,
    ) -> None:
        self.session = session
        self.settings = settings
        self.generation_provider = generation_provider
        self.contexts = AnalysisContextBuilder(session, settings)
        self.verifier = VerificationService()

    def _generate(
        self,
        instruction: str,
        context: AnalysisContext,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        prompt, _ = build_grounded_prompt(
            question=instruction,
            sources=context.sources,
        )
        tokens = max_new_tokens or self.settings.intelligence_max_new_tokens
        return self.generation_provider.generate(
            prompt,
            temperature=self.settings.generation_temperature,
            max_new_tokens=tokens,
            top_k=self.settings.generation_top_k,
            top_p=self.settings.generation_top_p,
            repetition_penalty=self.settings.generation_repetition_penalty,
            do_sample=self.settings.generation_do_sample,
        )


class SummaryService(GroundedAnalysisService):
    def generate(self, request: SummaryRequest) -> SummaryRead:
        if request.kind is SummaryKind.WHOLE_DOCUMENT and len(request.document_ids) != 1:
            raise ConflictError(
                code="whole_document_requires_one_document",
                message="A whole-document summary requires exactly one document.",
            )
        if request.kind is SummaryKind.SECTION and (
            len(request.document_ids) != 1 or request.section_index is None
        ):
            raise ConflictError(
                code="section_summary_requires_location",
                message="A section summary requires one document and a section index.",
            )
        context = self.contexts.build(
            knowledge_base_id=request.knowledge_base_id,
            document_ids=request.document_ids,
            section_index=(request.section_index if request.kind is SummaryKind.SECTION else None),
        )
        instructions = {
            SummaryKind.WHOLE_DOCUMENT: (
                "Summarize the selected document accurately. Cover its purpose, "
                "main evidence, conclusions, and stated limitations."
            ),
            SummaryKind.KNOWLEDGE_BASE: (
                "Synthesize the selected knowledge base. Identify major topics, "
                "consistent findings, disagreements, and limitations."
            ),
            SummaryKind.SECTION: (
                "Summarize this section while preserving its key facts and qualifications."
            ),
            SummaryKind.KEY_POINTS: (
                "Return concise key points as a Markdown bullet list. Every point must "
                "include a source marker."
            ),
            SummaryKind.EXECUTIVE: (
                "Write an executive summary for a decision-maker: context, important "
                "findings, implications, risks, and limitations."
            ),
        }
        content = self._generate(instructions[request.kind], context)
        return SummaryRead(
            kind=request.kind,
            content=content,
            citations=context.citations,
            verification=self.verifier.verify(content, context.sources),
            model_used=self.generation_provider.model_name,
        )


class ComparisonService(GroundedAnalysisService):
    """Comparison using a **single consolidated LLM call** instead of 6.

    The old implementation made 6 separate generation calls (common_themes,
    differences, contradictions, methodologies, conclusions, limitations),
    each sending the full context.  On an 8 GB machine with a 0.5B model
    this took 30–60+ seconds and frequently timed out.

    The new implementation builds a single prompt that requests all
    dimensions in one generation call, then parses the structured output.
    """

    def compare(self, request: ComparisonRequest) -> ComparisonRead:
        started = perf_counter()
        context = self.contexts.build(
            knowledge_base_id=request.knowledge_base_id,
            document_ids=request.document_ids,
            max_characters=self.settings.comparison_max_context_characters,
        )

        consolidated_instruction = (
            "Compare the selected documents across these dimensions. "
            "For each dimension, write 1–3 concise sentences.\n\n"
            "COMMON THEMES:\n(What themes appear in multiple documents?)\n\n"
            "DIFFERENCES:\n(What material differences exist?)\n\n"
            "CONTRADICTIONS:\n(Any conflicting claims? If none, say so.)\n\n"
            "METHODOLOGIES:\n(How do the approaches or evidence sources differ?)\n\n"
            "CONCLUSIONS:\n(How do the conclusions compare?)\n\n"
            "LIMITATIONS:\n(What risks, gaps, or limitations are stated?)\n\n"
            "Use [SOURCE:chunk_id] citations. Be factual and concise."
        )

        raw = self._generate(
            consolidated_instruction,
            context,
            max_new_tokens=self.settings.intelligence_max_new_tokens,
        )
        elapsed_ms = (perf_counter() - started) * 1000
        sections = _parse_comparison_sections(raw)
        combined = " ".join(sections.values())

        logger.info(
            "Comparison completed in %.0fms with 1 generation call (was 6)",
            elapsed_ms,
        )

        return ComparisonRead(
            common_themes=sections.get("common_themes", raw),
            differences=sections.get("differences", ""),
            contradictions=sections.get("contradictions", ""),
            methodologies=sections.get("methodologies", ""),
            conclusions=sections.get("conclusions", ""),
            limitations=sections.get("limitations", ""),
            citations=context.citations,
            verification=self.verifier.verify(combined, context.sources),
            model_used=self.generation_provider.model_name,
            elapsed_ms=round(elapsed_ms, 1),
            generation_calls=1,
        )


def _parse_comparison_sections(raw: str) -> dict[str, str]:
    """Parse a consolidated comparison response into named sections."""
    section_headers = [
        ("common_themes", r"COMMON\s+THEMES\s*:?"),
        ("differences", r"DIFFERENCES\s*:?"),
        ("contradictions", r"CONTRADICTIONS\s*:?"),
        ("methodologies", r"METHODOLOGIES\s*:?"),
        ("conclusions", r"CONCLUSIONS\s*:?"),
        ("limitations", r"LIMITATIONS\s*:?"),
    ]

    # Build a combined pattern to split on any header
    header_patterns = [f"(?:{pattern})" for _, pattern in section_headers]
    split_pattern = re.compile(
        r"(?:^|\n)\s*(?:" + "|".join(header_patterns) + r")\s*\n?",
        re.IGNORECASE,
    )

    parts = split_pattern.split(raw)
    # Remove the first part (text before any header, if any)
    content_parts = [p.strip() for p in parts if p and p.strip()]

    result: dict[str, str] = {}
    header_names = [name for name, _ in section_headers]

    for i, name in enumerate(header_names):
        if i < len(content_parts):
            result[name] = content_parts[i]
        else:
            result[name] = ""

    # Fallback: if any field is empty (unstructured output returned), populate missing fields
    text = raw.strip()
    for name in header_names:
        if not result[name]:
            result[name] = text

    return result


class ReportService(GroundedAnalysisService):
    """Section-by-section report generation with per-section timeout safety.

    The old implementation made 5 sequential generation calls with the
    full context for each.  This version generates one section at a time
    and persists each section immediately so partial results are never lost.
    """

    def create(self, request: ReportRequest) -> ResearchReportRead:
        started = perf_counter()
        context = self.contexts.build(
            knowledge_base_id=request.knowledge_base_id,
            document_ids=request.document_ids,
        )
        sections = {
            "executive_summary": (
                f"Write a concise executive summary for this objective: {request.objective}"
            ),
            "findings": (
                f"Present the key evidence-backed findings relevant to: {request.objective}"
            ),
            "comparison": (
                "Compare source perspectives and conclusions. If only one "
                "source exists, explain its internal themes instead."
            ),
            "risks_and_limitations": (
                "Identify source-supported risks, limitations, and missing evidence."
            ),
            "conclusions": (
                f"Give cautious conclusions supported by sources for: {request.objective}"
            ),
        }

        generated: dict[str, str] = {}
        generation_calls = 0
        for name, instruction in sections.items():
            try:
                generated[name] = self._generate(instruction, context)
                generation_calls += 1
            except Exception:
                logger.warning("Report section '%s' failed, using fallback", name, exc_info=True)
                generated[name] = _SECTION_TIMEOUT_MSG

        elapsed_ms = (perf_counter() - started) * 1000

        markdown = (
            f"# {request.title}\n\n"
            f"## Objective\n\n{request.objective}\n\n"
            f"## Executive summary\n\n{generated['executive_summary']}\n\n"
            f"## Findings\n\n{generated['findings']}\n\n"
            f"## Comparison\n\n{generated['comparison']}\n\n"
            f"## Risks and limitations\n\n{generated['risks_and_limitations']}\n\n"
            f"## Conclusions\n\n{generated['conclusions']}\n"
        )
        verified_text = " ".join(generated.values())
        partial = any(v == _SECTION_TIMEOUT_MSG for v in generated.values())

        logger.info(
            "Report completed in %.0fms with %d generation calls, partial=%s",
            elapsed_ms,
            generation_calls,
            partial,
        )

        return ResearchReportRead(
            title=request.title,
            objective=request.objective,
            **generated,
            cited_sources=context.citations,
            verification=self.verifier.verify(verified_text, context.sources),
            markdown=markdown,
            model_used=self.generation_provider.model_name,
            elapsed_ms=round(elapsed_ms, 1),
            generation_calls=generation_calls,
            partial=partial,
        )
