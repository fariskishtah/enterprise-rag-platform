from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import replace
from difflib import SequenceMatcher

from app.ai.vectorstores.base import VectorSearchResult
from app.core.config import Settings

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]*")
STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "can",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "many",
    "much",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "which",
    "who",
    "with",
}


def normalized_tokens(text: str, *, keep_stopwords: bool = False) -> list[str]:
    tokens = [token.lower().strip("'_-") for token in TOKEN_PATTERN.findall(text)]
    if keep_stopwords:
        return [token for token in tokens if token]
    return [token for token in tokens if token and token not in STOPWORDS and len(token) > 1]


def token_set(text: str) -> set[str]:
    return set(normalized_tokens(text))


class HybridReranker:
    """Fuse dense similarity with transparent lexical and direct-relevance scores."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def rerank(
        self,
        *,
        query: str,
        candidates: list[VectorSearchResult],
        top_k: int,
    ) -> list[VectorSearchResult]:
        if not candidates:
            return []
        query_tokens = normalized_tokens(query)
        query_terms = set(query_tokens)
        if not query_terms:
            return candidates[:top_k]

        tokenized = [normalized_tokens(candidate.text) for candidate in candidates]
        document_frequency = Counter(
            term for tokens in tokenized for term in set(tokens) if term in query_terms
        )
        average_length = sum(len(tokens) for tokens in tokenized) / max(1, len(tokenized))
        maximum_bm25 = 0.0
        raw_lexical: list[float] = []
        direct_scores: list[float] = []
        coverages: list[float] = []

        for tokens in tokenized:
            counts = Counter(tokens)
            length = max(1, len(tokens))
            bm25 = 0.0
            for term in query_terms:
                frequency = counts[term]
                if frequency == 0:
                    continue
                document_count = len(candidates)
                df = document_frequency[term]
                inverse_frequency = math.log(1 + (document_count - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.2 * (0.25 + 0.75 * length / max(1.0, average_length))
                bm25 += inverse_frequency * frequency * 2.2 / denominator
            raw_lexical.append(bm25)
            maximum_bm25 = max(maximum_bm25, bm25)

            candidate_terms = set(tokens)
            coverage = len(query_terms & candidate_terms) / len(query_terms)
            coverages.append(coverage)
            query_phrase = " ".join(normalized_tokens(query, keep_stopwords=True))
            candidate_phrase = " ".join(tokens)
            sequence = SequenceMatcher(None, query_phrase, candidate_phrase[:2000]).ratio()
            bigrams = set(zip(query_tokens, query_tokens[1:], strict=False))
            candidate_bigrams = set(zip(tokens, tokens[1:], strict=False))
            bigram_score = len(bigrams & candidate_bigrams) / len(bigrams) if bigrams else coverage
            direct_scores.append(min(1.0, 0.65 * coverage + 0.25 * bigram_score + 0.1 * sequence))

        weighted_total = (
            self.settings.dense_score_weight
            + self.settings.lexical_score_weight
            + self.settings.rerank_score_weight
        )
        scored: list[VectorSearchResult] = []
        for candidate, lexical_raw, rerank, coverage in zip(
            candidates, raw_lexical, direct_scores, coverages, strict=True
        ):
            lexical = lexical_raw / maximum_bm25 if maximum_bm25 else 0.0
            dense = max(0.0, min(1.0, (candidate.score + 1.0) / 2.0))
            combined = (
                self.settings.dense_score_weight * dense
                + self.settings.lexical_score_weight * lexical
                + self.settings.rerank_score_weight * rerank
            ) / weighted_total
            scored.append(
                replace(
                    candidate,
                    score=combined,
                    dense_score=candidate.score,
                    lexical_score=lexical,
                    reranking_score=rerank,
                    query_coverage=coverage,
                )
            )

        scored.sort(
            key=lambda item: (
                -item.score,
                -item.query_coverage,
                -(item.dense_score or -1.0),
                item.chunk_id,
            )
        )
        return self._deduplicate_and_diversify(scored, top_k)

    def _deduplicate_and_diversify(
        self, candidates: list[VectorSearchResult], top_k: int
    ) -> list[VectorSearchResult]:
        selected: list[VectorSearchResult] = []
        per_document: Counter[str] = Counter()
        for candidate in candidates:
            candidate_terms = token_set(candidate.text)
            if any(
                self._jaccard(candidate_terms, token_set(previous.text))
                >= self.settings.near_duplicate_threshold
                for previous in selected
            ):
                continue
            if per_document[candidate.document_id] >= self.settings.maximum_sources_per_document:
                continue
            selected.append(candidate)
            per_document[candidate.document_id] += 1
            if len(selected) >= top_k:
                break
        return selected

    @staticmethod
    def _jaccard(first: set[str], second: set[str]) -> float:
        union = first | second
        return len(first & second) / len(union) if union else 1.0
