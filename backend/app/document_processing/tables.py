"""Structured table extraction module for PDF and DOCX files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractedTable:
    table_id: str
    page_number: int | None
    headers: list[str]
    rows: list[list[str]]
    markdown: str
    extraction_method: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class TableExtractor:
    """Extracts grid-structured tables from PDF documents using pdfplumber."""

    def extract_pdf_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                for page_index, page in enumerate(pdf.pages, start=1):
                    extracted = page.extract_tables()
                    for table_idx, raw_table in enumerate(extracted, start=1):
                        clean_rows = [
                            [str(cell or "").strip() for cell in row]
                            for row in raw_table
                            if any(row)
                        ]
                        if not clean_rows:
                            continue
                        headers = clean_rows[0]
                        data_rows = clean_rows[1:] if len(clean_rows) > 1 else []
                        markdown_parts = [
                            "| " + " | ".join(headers) + " |",
                            "| " + " | ".join(["---"] * len(headers)) + " |",
                        ]
                        for r in data_rows:
                            markdown_parts.append("| " + " | ".join(r) + " |")
                        markdown_str = "\n".join(markdown_parts)

                        table_id = f"table-p{page_index}-t{table_idx}"
                        tables.append(
                            ExtractedTable(
                                table_id=table_id,
                                page_number=page_index,
                                headers=headers,
                                rows=data_rows,
                                markdown=markdown_str,
                                extraction_method="pdfplumber_grid",
                                confidence=0.9,
                                metadata={
                                    "table_id": table_id,
                                    "page_number": page_index,
                                    "row_count": len(clean_rows),
                                    "col_count": len(headers),
                                },
                            )
                        )
        except Exception:
            logger.warning("pdfplumber table extraction failed for %s", pdf_path, exc_info=True)
        return tables
