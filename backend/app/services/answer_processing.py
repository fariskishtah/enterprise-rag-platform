from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.vectorstores.base import VectorSearchResult
from app.services.reranking import token_set

SOURCE_MARKER_PATTERN = re.compile(r"\[SOURCE:([^\]]+)\]", re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n{2,}")
NOT_FOUND_ANSWER = (
    "The supplied documents do not contain enough information to answer this question."
)


@dataclass(frozen=True)
class ProcessedAnswer:
    direct_answer: str
    supporting_explanation: str
    visible_answer: str
    cited_chunk_ids: list[str]
    copied_context_ratio: float


class AnswerPostProcessor:
    def process(
        self,
        *,
        question: str,
        raw_answer: str,
        sources: list[VectorSearchResult],
        response_mode: str,
    ) -> ProcessedAnswer:
        cited_ids = list(dict.fromkeys(SOURCE_MARKER_PATTERN.findall(raw_answer)))
        cleaned = SOURCE_MARKER_PATTERN.sub("", raw_answer)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            cleaned = NOT_FOUND_ANSWER

        unique_sentences: list[str] = []
        normalized_seen: set[str] = set()
        for sentence in SENTENCE_SPLIT_PATTERN.split(cleaned):
            value = sentence.strip()
            if not value:
                continue
            normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
            if normalized and normalized not in normalized_seen:
                normalized_seen.add(normalized)
                unique_sentences.append(value)

        limit = self._sentence_limit(question, response_mode)
        unique_sentences = unique_sentences[:limit]
        visible = " ".join(unique_sentences).strip() or NOT_FOUND_ANSWER
        direct = unique_sentences[0] if unique_sentences else NOT_FOUND_ANSWER
        explanation = " ".join(unique_sentences[1:])
        copied_ratio = self._copied_context_ratio(visible, sources)
        return ProcessedAnswer(
            direct_answer=direct,
            supporting_explanation=explanation,
            visible_answer=visible,
            cited_chunk_ids=cited_ids,
            copied_context_ratio=copied_ratio,
        )

    @staticmethod
    def _sentence_limit(question: str, response_mode: str) -> int:
        if response_mode == "detailed":
            return 8
        normalized = question.lower()
        if any(term in normalized for term in ("compare", "difference", "versus", " vs ")):
            return 5
        if any(term in normalized for term in ("list", "which", "what are")):
            return 4
        return 2

    @staticmethod
    def _copied_context_ratio(answer: str, sources: list[VectorSearchResult]) -> float:
        answer_tokens = token_set(answer)
        if not answer_tokens:
            return 0.0
        source_tokens = token_set(" ".join(source.text for source in sources))
        return len(answer_tokens & source_tokens) / len(answer_tokens)


def supporting_sources(
    answer: str,
    sources: list[VectorSearchResult],
    requested_ids: list[str],
) -> list[VectorSearchResult]:
    answer_terms = token_set(answer)
    by_id = {source.chunk_id: source for source in sources}
    selected: list[VectorSearchResult] = [
        by_id[chunk_id] for chunk_id in requested_ids if chunk_id in by_id
    ]
    if not selected:
        ranked: list[tuple[float, VectorSearchResult]] = []
        for source in sources:
            source_terms = token_set(source.text)
            support = len(answer_terms & source_terms) / max(1, len(answer_terms))
            if support >= 0.3:
                ranked.append((support, source))
        ranked.sort(key=lambda item: (-item[0], -item[1].score))
        selected = [source for _, source in ranked[:2]]
    return selected
