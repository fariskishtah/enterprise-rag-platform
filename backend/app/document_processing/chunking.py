from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.document_processing.extraction import ExtractedSection


@dataclass(frozen=True)
class ChunkData:
    id: str
    document_id: str
    knowledge_base_id: str
    chunk_index: int
    text: str
    page_number: int | None
    section_index: int | None
    start_char: int
    end_char: int
    character_count: int
    token_estimate: int
    metadata: dict[str, Any]


class TextChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(
        self,
        *,
        document_id: str,
        knowledge_base_id: str,
        sections: list[ExtractedSection],
    ) -> list[ChunkData]:
        chunks: list[ChunkData] = []
        for section in sections:
            section_offset = 0
            while section_offset < len(section.text):
                proposed_end = min(section_offset + self.chunk_size, len(section.text))
                end = self._natural_boundary(section.text, section_offset, proposed_end)
                raw = section.text[section_offset:end]
                left_trim = len(raw) - len(raw.lstrip())
                right_trimmed = raw.rstrip()
                if right_trimmed:
                    local_start = section_offset + left_trim
                    local_end = section_offset + len(right_trimmed)
                    text = section.text[local_start:local_end]
                    absolute_start = section.start_char + local_start
                    absolute_end = section.start_char + local_end
                    chunk_index = len(chunks)
                    digest = hashlib.sha256(
                        (
                            f"{document_id}:{chunk_index}:{absolute_start}:{absolute_end}:{text}"
                        ).encode()
                    ).hexdigest()
                    chunks.append(
                        ChunkData(
                            id=digest,
                            document_id=document_id,
                            knowledge_base_id=knowledge_base_id,
                            chunk_index=chunk_index,
                            text=text,
                            page_number=section.page_number,
                            section_index=section.section_index,
                            start_char=absolute_start,
                            end_char=absolute_end,
                            character_count=len(text),
                            token_estimate=max(1, (len(text) + 3) // 4),
                            metadata={
                                **section.metadata,
                                "heading": section.heading,
                                "section_index": section.section_index,
                            },
                        )
                    )
                if end >= len(section.text):
                    break
                next_offset = end - self.chunk_overlap
                section_offset = max(
                    section_offset + 1,
                    self._natural_start(
                        section.text,
                        max(section_offset + 1, next_offset),
                        end,
                    ),
                )
        return chunks

    def _natural_boundary(self, text: str, start: int, proposed_end: int) -> int:
        if proposed_end >= len(text):
            return len(text)
        minimum = start + int(self.chunk_size * 0.6)
        sentence_boundaries = [
            text.rfind("\n", minimum, proposed_end),
            text.rfind(". ", minimum, proposed_end),
        ]
        boundary = max(sentence_boundaries)
        if boundary > start:
            return boundary + (2 if text[boundary : boundary + 2] in {". ", ".\n"} else 1)

        if boundary <= start:
            forward_limit = min(len(text), proposed_end + self.chunk_size // 2)
            forward_candidates = [
                value
                for value in (
                    text.find("\n", proposed_end, forward_limit),
                    text.find(". ", proposed_end, forward_limit),
                    text.find(".\n", proposed_end, forward_limit),
                )
                if value >= 0
            ]
            if forward_candidates:
                forward = min(forward_candidates)
                return forward + (2 if text[forward : forward + 2] in {". ", ".\n"} else 1)
        word_boundary = text.rfind(" ", minimum, proposed_end)
        return word_boundary + 1 if word_boundary > start else proposed_end

    @staticmethod
    def _natural_start(text: str, proposed_start: int, previous_end: int) -> int:
        """Avoid overlap windows that begin in the middle of a sentence or word."""

        boundary_candidates = [
            value
            for value in (
                text.find("\n", proposed_start, previous_end),
                text.find(". ", proposed_start, previous_end),
                text.find(".\n", proposed_start, previous_end),
            )
            if value >= 0
        ]
        if boundary_candidates:
            boundary = min(boundary_candidates)
            return boundary + (2 if text[boundary : boundary + 2] in {". ", ".\n"} else 1)
        previous_boundary = max(
            text.rfind("\n", 0, proposed_start),
            text.rfind(". ", 0, proposed_start),
            text.rfind(".\n", 0, proposed_start),
        )
        if previous_boundary >= 0:
            return previous_boundary + (
                2 if text[previous_boundary : previous_boundary + 2] in {". ", ".\n"} else 1
            )
        previous_word_boundary = text.rfind(" ", 0, proposed_start)
        if previous_word_boundary >= 0:
            return previous_word_boundary + 1
        while proposed_start < previous_end and not text[proposed_start].isspace():
            proposed_start += 1
        return min(previous_end, proposed_start + 1)
