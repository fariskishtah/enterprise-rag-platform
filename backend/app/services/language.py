"""Language detection and Arabic NLP utilities."""

from __future__ import annotations

import re

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


def detect_language(text: str) -> str:
    """Detect whether text is primarily Arabic ('ar') or English ('en')."""
    if not text or not text.strip():
        return "en"

    arabic_chars = len(ARABIC_RE.findall(text))
    total_chars = max(1, len(text.strip()))

    if arabic_chars / total_chars > 0.15:
        return "ar"
    return "en"
