from __future__ import annotations

import gc
import hashlib
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar

from app.core.errors import ProcessingError
from app.services.language import transcription_language


@dataclass(frozen=True)
class TranscribedSegment:
    index: int
    start: float
    end: float
    text: str
    language: str | None
    confidence: float | None


@dataclass(frozen=True)
class TranscriptionResult:
    segments: list[TranscribedSegment]
    language: str | None
    language_probability: float | None
    model_name: str


class TranscriptionProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def transcribe(
        self, media_path: Path, *, language: str | None = None
    ) -> TranscriptionResult: ...


class FasterWhisperTranscriptionProvider(TranscriptionProvider):
    _models: ClassVar[dict[tuple[str, str, str, str, int, int], Any]] = {}
    _states: ClassVar[dict[tuple[str, str, str, str, int, int], str]] = {}
    _lock: ClassVar[Lock] = Lock()

    def __init__(
        self,
        *,
        model_name: str,
        cache_path: Path,
        device: str,
        compute_type: str,
        cpu_threads: int,
        num_workers: int = 1,
        beam_size: int = 3,
    ) -> None:
        self._model_name = model_name
        self.cache_path = cache_path
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers
        self.beam_size = beam_size

    @property
    def model_name(self) -> str:
        return f"faster-whisper/{self._model_name}"

    def _cache_key(self) -> tuple[str, str, str, str, int, int]:
        return (
            self._model_name,
            str(self.cache_path.resolve()),
            self.device,
            self.compute_type,
            self.cpu_threads,
            self.num_workers,
        )

    @property
    def load_status(self) -> str:
        key = self._cache_key()
        return "ready" if key in self._models else self._states.get(key, "cold")

    def unload(self) -> bool:
        """Release this CPU model after use on constrained production profiles."""

        key = self._cache_key()
        with self._lock:
            removed = self._models.pop(key, None) is not None
            self._states[key] = "cold"
        if removed:
            gc.collect()
        return removed

    def _load_model(self) -> Any:
        key = self._cache_key()
        if key in self._models:
            return self._models[key]
        with self._lock:
            if key in self._models:
                return self._models[key]
            try:
                self._states[key] = "loading"
                from faster_whisper import WhisperModel

                self.cache_path.mkdir(parents=True, exist_ok=True)
                model = WhisperModel(
                    self._model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.cpu_threads,
                    num_workers=self.num_workers,
                    download_root=str(self.cache_path),
                )
            except Exception as exc:
                self._states[key] = "failed"
                raise ProcessingError(
                    "The local transcription model could not be loaded. Install the media "
                    "dependencies or select a cached Whisper model.",
                    code="transcription_model_unavailable",
                ) from exc
            self._models[key] = model
            self._states[key] = "ready"
            return model

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        try:
            raw_segments, info = self._load_model().transcribe(
                str(media_path),
                language=transcription_language(language),
                task="transcribe",
                beam_size=self.beam_size,
                vad_filter=True,
                word_timestamps=False,
                condition_on_previous_text=True,
            )
            segments = [
                TranscribedSegment(
                    index=index,
                    start=float(segment.start),
                    end=float(segment.end),
                    text=" ".join(segment.text.strip().split()),
                    language=info.language,
                    confidence=(
                        max(0.0, min(1.0, math.exp(segment.avg_logprob)))
                        if segment.avg_logprob is not None
                        else None
                    ),
                )
                for index, segment in enumerate(raw_segments)
                if segment.text.strip()
            ]
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError(
                "Local transcription failed. Confirm that the media contains a readable "
                "audio stream and retry.",
                code="transcription_failed",
            ) from exc
        if not segments:
            raise ProcessingError(
                "No speech was detected in this media.",
                code="no_speech_detected",
            )
        return TranscriptionResult(
            segments=segments,
            language=info.language,
            language_probability=float(info.language_probability),
            model_name=self.model_name,
        )


TIMESTAMP_PATTERN = re.compile(
    r"(?P<sh>\d{1,2}):(?P<sm>\d{2}):(?P<ss>\d{2}(?:[.,]\d+)?)\s*-->\s*"
    r"(?P<eh>\d{1,2}):(?P<em>\d{2}):(?P<es>\d{2}(?:[.,]\d+)?)"
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def subtitle_segments(path: Path, language: str | None = None) -> list[TranscribedSegment]:
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    segments: list[TranscribedSegment] = []
    index = 0
    while index < len(lines):
        match = TIMESTAMP_PATTERN.search(lines[index])
        if match is None:
            index += 1
            continue
        start = _timestamp_seconds(match, "s")
        end = _timestamp_seconds(match, "e")
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            value = TAG_PATTERN.sub("", lines[index]).strip()
            if value and value not in text_lines:
                text_lines.append(value)
            index += 1
        text = " ".join(text_lines).strip()
        if text:
            segments.append(
                TranscribedSegment(
                    index=len(segments),
                    start=start,
                    end=end,
                    text=text,
                    language=language,
                    confidence=1.0,
                )
            )
    return segments


def _timestamp_seconds(match: re.Match[str], prefix: str) -> float:
    hours = int(match.group(f"{prefix}h"))
    minutes = int(match.group(f"{prefix}m"))
    seconds = float(match.group(f"{prefix}s").replace(",", "."))
    return hours * 3600 + minutes * 60 + seconds


def stable_segment_id(media_source_id: str, index: int, text: str) -> str:
    return hashlib.sha256(f"{media_source_id}:{index}:{text}".encode()).hexdigest()
