"""Language detection and Arabic NLP utilities."""

from __future__ import annotations

import re
from typing import Literal

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
OutputLanguage = Literal["auto", "ar", "en"]

NOT_FOUND_ANSWERS = {
    "en": "The supplied documents do not contain enough information to answer this question.",
    "ar": "لا تحتوي المستندات المقدمة على معلومات كافية للإجابة عن هذا السؤال.",
}


def detect_language(text: str) -> str:
    """Detect whether text is primarily Arabic ('ar') or English ('en')."""
    if not text or not text.strip():
        return "en"

    arabic_chars = len(ARABIC_RE.findall(text))
    total_chars = max(1, len(text.strip()))

    if arabic_chars / total_chars > 0.15:
        return "ar"
    return "en"


def resolve_output_language(preference: OutputLanguage, source_text: str) -> Literal["ar", "en"]:
    """Resolve an explicit output language or infer it from the user's text."""

    return detect_language(source_text) if preference == "auto" else preference


def not_found_answer(language: str) -> str:
    return NOT_FOUND_ANSWERS["ar" if language == "ar" else "en"]


def transcription_language(value: str | None) -> Literal["ar", "en"] | None:
    """Translate the public ``auto`` mode to faster-whisper's detection value."""

    normalized = (value or "auto").strip().lower()
    if normalized == "auto":
        return None
    if normalized in {"ar", "en"}:
        return normalized
    raise ValueError("Transcription language must be auto, ar, or en.")
