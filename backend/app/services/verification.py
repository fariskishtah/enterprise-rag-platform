from __future__ import annotations

import re

from app.ai.vectorstores.base import VectorSearchResult
from app.schemas.rag import (
    ClaimSupportStatus,
    VerificationRead,
    VerificationStatus,
)

WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
SOURCE_MARKER_PATTERN = re.compile(r"\[SOURCE:[^\]]+\]")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_PATTERN.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 2
    }


class VerificationService:
    def verify(self, answer: str, sources: list[VectorSearchResult]) -> VerificationRead:
        if not answer.strip() or "do not contain enough information" in answer.lower():
            return VerificationRead(
                status=VerificationStatus.UNSUPPORTED,
                claim_support=ClaimSupportStatus.MISSING_ANSWER,
                explanation="The answer correctly reports that no supported answer was found.",
                unsupported_statements=[],
            )
        if not sources:
            return VerificationRead(
                status=VerificationStatus.UNSUPPORTED,
                claim_support=ClaimSupportStatus.UNSUPPORTED,
                explanation="No retrieved source passages were available for verification.",
                unsupported_statements=[answer] if answer.strip() else [],
            )
        statements = [
            SOURCE_MARKER_PATTERN.sub("", statement).strip()
            for statement in SENTENCE_PATTERN.split(answer)
            if statement.strip()
        ]
        scored: list[tuple[str, float]] = []
        contradiction_detected = False
        for statement in statements:
            claim_tokens = _meaningful_tokens(statement)
            if not claim_tokens:
                continue
            claim_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", statement))
            best_support = 0.0
            best_conflict = 0.0
            for source in sources:
                passages = [
                    value.strip() for value in SENTENCE_PATTERN.split(source.text) if value.strip()
                ] or [source.text]
                for passage in passages:
                    source_tokens = _meaningful_tokens(passage)
                    raw_support = len(claim_tokens & source_tokens) / len(claim_tokens)
                    source_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", passage))
                    number_conflict = bool(
                        claim_numbers
                        and source_numbers
                        and not claim_numbers.issubset(source_numbers)
                    )
                    statement_negated = bool(re.search(r"\b(?:not|never|no)\b", statement.lower()))
                    source_negated = bool(re.search(r"\b(?:not|never|no)\b", passage.lower()))
                    negation_conflict = raw_support >= 0.55 and statement_negated != source_negated
                    if number_conflict or negation_conflict:
                        best_conflict = max(best_conflict, raw_support)
                        raw_support *= 0.2 if negation_conflict else 0.25
                    best_support = max(best_support, raw_support)
            if best_conflict >= 0.55 and best_conflict > best_support:
                contradiction_detected = True
            scored.append((statement, best_support))

        if not scored:
            return VerificationRead(
                status=VerificationStatus.UNSUPPORTED,
                claim_support=ClaimSupportStatus.UNSUPPORTED,
                explanation="The answer contained no verifiable factual statement.",
                unsupported_statements=statements,
            )
        unsupported = [statement for statement, score in scored if score < 0.45]
        supported = [statement for statement, score in scored if score >= 0.45]
        average = sum(score for _, score in scored) / len(scored)
        if contradiction_detected:
            status = VerificationStatus.UNSUPPORTED
            claim_support = ClaimSupportStatus.CONTRADICTION_DETECTED
            explanation = "A generated claim conflicts with a retrieved passage."
        elif not unsupported and average >= 0.6:
            status = VerificationStatus.SUPPORTED
            claim_support = ClaimSupportStatus.FULLY_SUPPORTED
            explanation = "Every factual claim is supported by an individual cited passage."
        elif len(unsupported) < len(scored) and average >= 0.35:
            status = VerificationStatus.PARTIALLY_SUPPORTED
            claim_support = ClaimSupportStatus.PARTIALLY_SUPPORTED
            explanation = (
                "Some factual claims have direct support, while others need stronger evidence."
            )
        else:
            status = VerificationStatus.UNSUPPORTED
            claim_support = ClaimSupportStatus.UNSUPPORTED
            explanation = "The answer is not sufficiently supported by the retrieved passages."
        return VerificationRead(
            status=status,
            claim_support=claim_support,
            explanation=explanation,
            unsupported_statements=unsupported,
            supported_statements=supported,
            contradiction_detected=contradiction_detected,
            claim_scores={statement: round(score, 4) for statement, score in scored},
        )
