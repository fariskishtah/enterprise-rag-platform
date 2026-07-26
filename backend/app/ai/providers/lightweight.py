from __future__ import annotations

import hashlib
import re

import numpy as np

from app.ai.interfaces import EmbeddingProvider, GenerationProvider

TOKEN_PATTERN = re.compile(r"[^\W_][\w-]*", re.UNICODE)


class HashingEmbeddingProvider(EmbeddingProvider):
    """Dependency-light real embedding algorithm for tests and offline diagnostics.

    The production default remains Sentence Transformers. This provider performs signed
    feature hashing over normalized tokens and is useful for deterministic integration
    tests without downloading a model.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    @property
    def model_name(self) -> str:
        return f"local-hashing-{self.dimension}"

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        tokens = TOKEN_PATTERN.findall(text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.stack([self._embed(text) for text in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)


class ExtractiveGenerationProvider(GenerationProvider):
    """Deterministic local integration provider that extracts supplied source text.

    It is never selected by default and exists so the complete pipeline can be exercised
    in tests without mocking or downloading a generative model.
    """

    @property
    def model_name(self) -> str:
        return "local-extractive-integration"

    def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        top_k: int = 50,
        top_p: float = 0.9,
        repetition_penalty: float = 1.0,
        do_sample: bool | None = None,
    ) -> str:
        del temperature, top_k, top_p, repetition_penalty, do_sample
        source_pattern = re.compile(
            r"\[BEGIN_UNTRUSTED_SOURCE (?P<id>[^\]]+)\]\n"
            r"(?P<text>.*?)\n\[END_UNTRUSTED_SOURCE\]",
            re.DOTALL,
        )
        matches = list(source_pattern.finditer(prompt))
        if not matches:
            return "The supplied documents do not contain enough information to answer."
        question_match = re.search(
            r"User question:\s*(?P<question>.*?)\s*Grounded answer:",
            prompt,
            re.DOTALL,
        )
        question = question_match.group("question") if question_match else ""
        question_terms = {
            _normalize_term(token)
            for token in TOKEN_PATTERN.findall(question.lower())
            if len(token) > 2
            and token
            not in {"what", "when", "where", "which", "who", "how", "many", "much", "does"}
        }
        ranked: list[tuple[float, str, str]] = []
        for match in matches:
            raw_text = match.group("text")
            content = re.split(r"\nLocation:.*?\n", raw_text, maxsplit=1)[-1]
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", content):
                sentence = " ".join(sentence.strip().split())
                if not sentence or sentence.startswith(("Document:", "Location:")):
                    continue
                terms = {
                    _normalize_term(token) for token in TOKEN_PATTERN.findall(sentence.lower())
                }
                overlap = len(question_terms & terms) / max(1, len(question_terms))
                ranked.append((overlap, sentence, match.group("id")))
        ranked.sort(key=lambda value: (-value[0], len(value[1])))
        if not ranked:
            return "The supplied documents do not contain enough information to answer."
        best_score = ranked[0][0]
        minimum_score = best_score * 0.7 if best_score > 0 else 0
        selected = [value for value in ranked if value[0] >= minimum_score][:2]
        answer = " ".join(f"{sentence} [SOURCE:{source_id}]" for _, sentence, source_id in selected)
        maximum_characters = max(120, max_new_tokens * 4)
        if len(answer) > maximum_characters:
            return answer[:maximum_characters].rsplit(" ", 1)[0]
        return answer


def _normalize_term(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        return token[:-1]
    return token
