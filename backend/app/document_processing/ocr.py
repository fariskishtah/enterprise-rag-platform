"""OCR fallback module for scanned documents and image-based PDF pages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrPageResult:
    page_number: int
    text: str
    confidence: float
    ocr_engine: str
    ocr_language: str
    warnings: list[str]


class OcrEngine:
    """Tesseract OCR wrapper with graceful environment fallback."""

    def __init__(self, primary_language: str = "eng+ara") -> None:
        self.primary_language = primary_language
        self._tesseract_available: bool | None = None

    @property
    def is_available(self) -> bool:
        if self._tesseract_available is None:
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                self._tesseract_available = True
            except Exception:
                logger.info("Tesseract binary not detected on system PATH. OCR fallback disabled.")
                self._tesseract_available = False
        return self._tesseract_available

    def process_pdf_page(self, pdf_path: Path, page_number: int) -> OcrPageResult:
        warnings: list[str] = []
        if not self.is_available:
            warnings.append(
                f"Page {page_number} appears to be scanned but OCR engine "
                "(Tesseract) is unavailable."
            )
            return OcrPageResult(
                page_number=page_number,
                text="",
                confidence=0.0,
                ocr_engine="none",
                ocr_language=self.primary_language,
                warnings=warnings,
            )

        try:
            import pytesseract
            from pdf2image import convert_from_path

            images = convert_from_path(
                pdf_path,
                first_page=page_number,
                last_page=page_number,
                dpi=200,
            )
            if not images:
                warnings.append(f"Could not render page {page_number} image for OCR.")
                return OcrPageResult(
                    page_number=page_number,
                    text="",
                    confidence=0.0,
                    ocr_engine="tesseract",
                    ocr_language=self.primary_language,
                    warnings=warnings,
                )

            ocr_text = pytesseract.image_to_string(images[0], lang=self.primary_language).strip()
            return OcrPageResult(
                page_number=page_number,
                text=ocr_text,
                confidence=0.85 if ocr_text else 0.0,
                ocr_engine="tesseract",
                ocr_language=self.primary_language,
                warnings=warnings,
            )
        except Exception as exc:
            warnings.append(f"OCR failed for page {page_number}: {type(exc).__name__}")
            return OcrPageResult(
                page_number=page_number,
                text="",
                confidence=0.0,
                ocr_engine="tesseract",
                ocr_language=self.primary_language,
                warnings=warnings,
            )
