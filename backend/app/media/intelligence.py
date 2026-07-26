from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass

from app.media.transcription import TranscribedSegment

SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
ENTITY_PATTERN = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[A-Z]{2,})\b")
ACTION_PATTERN = re.compile(
    r"\b(?:action|must|should|will|need to|needs to|follow up|assigned to)\b", re.IGNORECASE
)
DECISION_PATTERN = re.compile(r"\b(?:decided|agreed|approved|selected)\b", re.IGNORECASE)
ISSUE_PATTERN = re.compile(
    r"\b(?:unresolved|unknown|open question|blocked|risk|issue)\b", re.IGNORECASE
)
DEFINITION_PATTERN = re.compile(
    r"\b(?P<term>[A-Za-z][A-Za-z -]{2,40})\s+(?:is|means|refers to)\s+(?P<value>[^.!?]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChapterValue:
    index: int
    start: float
    end: float
    title: str
    summary: str


class TranscriptIntelligenceService:
    model_name = "local-extractive-intelligence-v1"

    def analyze(
        self, segments: list[TranscribedSegment], language: str | None
    ) -> dict[str, object]:
        del language
        full_text = " ".join(segment.text for segment in segments)
        sentences = [
            sentence.strip() for sentence in SENTENCE_PATTERN.split(full_text) if sentence.strip()
        ]
        key_points = self._distinct(sentences)[:8]
        short_summary = " ".join(key_points[:2])
        detailed_summary = " ".join(key_points[:8])
        chapters = self._chapters(segments)
        action_items = [
            {
                "text": segment.text,
                "owner": None,
                "deadline": None,
                "timestamp": segment.start,
            }
            for segment in segments
            if ACTION_PATTERN.search(segment.text)
        ][:20]
        decisions = [sentence for sentence in sentences if DECISION_PATTERN.search(sentence)][:20]
        unresolved = [sentence for sentence in sentences if ISSUE_PATTERN.search(sentence)][:20]
        entity_counts = Counter(ENTITY_PATTERN.findall(full_text))
        entities = [
            {"name": name, "category": "mentioned_entity", "mentions": mentions}
            for name, mentions in entity_counts.most_common(20)
            if len(name) > 2
        ]
        definitions = {
            match.group("term").strip(): match.group("value").strip()
            for match in DEFINITION_PATTERN.finditer(full_text)
        }
        concepts = [
            value["name"]
            for value in entities
            if isinstance(value["name"], str) and value["name"].lower() not in {"the"}
        ][:10]
        glossary = {
            concept: definitions.get(concept, f"A concept mentioned in the transcript: {concept}.")
            for concept in concepts
        }
        quiz_questions = [
            f"What does the transcript say about {concept}?" for concept in concepts[:5]
        ]
        important_timestamps = [chapter.start for chapter in chapters]
        return {
            "short_summary": short_summary,
            "detailed_summary": detailed_summary,
            "key_points": key_points,
            "action_items": action_items,
            "decisions": decisions,
            "entities": entities,
            "important_quotes": [sentence[:180] for sentence in key_points[:5]],
            "lecture_outline": [chapter.title for chapter in chapters],
            "explained_concepts": concepts,
            "definitions": definitions,
            "examples": [
                sentence
                for sentence in sentences
                if re.search(r"\b(?:example|for instance|such as)\b", sentence, re.IGNORECASE)
            ][:10],
            "quiz_questions": quiz_questions,
            "revision_notes": key_points,
            "glossary": glossary,
            "important_timestamps": important_timestamps,
            "meeting_summary": short_summary,
            "unresolved_issues": unresolved,
            "chapters": chapters,
        }

    def _chapters(self, segments: list[TranscribedSegment]) -> list[ChapterValue]:
        if not segments:
            return []
        buckets: list[list[TranscribedSegment]] = []
        current: list[TranscribedSegment] = []
        bucket_start = segments[0].start
        for segment in segments:
            if current and segment.start - bucket_start >= 300:
                buckets.append(current)
                current = []
                bucket_start = segment.start
            current.append(segment)
        if current:
            buckets.append(current)

        chapters: list[ChapterValue] = []
        for index, bucket in enumerate(buckets):
            summary = " ".join(value.text for value in bucket[:3])
            title_words = re.findall(r"[A-Za-z][A-Za-z'-]+", summary)
            title = " ".join(title_words[:7]) or f"Chapter {index + 1}"
            digest = hashlib.sha256(summary.encode()).hexdigest()[:4]
            chapters.append(
                ChapterValue(
                    index=index,
                    start=bucket[0].start,
                    end=bucket[-1].end,
                    title=f"{title} · {digest}",
                    summary=summary[:500],
                )
            )
        return chapters

    @staticmethod
    def _distinct(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = re.sub(r"\W+", " ", value.lower()).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(value)
        return result
