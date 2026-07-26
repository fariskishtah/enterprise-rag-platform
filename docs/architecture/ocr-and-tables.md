# OCR & Table Extraction Architecture

EnterpriseRAG handles scanned PDF documents via Tesseract OCR fallback and parses structured tables via `pdfplumber`.

---

## OCR Fallback & Table Extraction Flow Diagram

```mermaid
flowchart TD
    PDF["PDF File Upload"] --> PYPDF["PyPDF Text Extractor"]
    PYPDF --> DENSITY_CHECK{"Page Text Density < 50 Chars?"}
    
    DENSITY_CHECK -- No (Digital Page) --> PLAIN_TEXT["Use Extracted Digital Text"]
    DENSITY_CHECK -- Yes (Scanned Page) --> PDF2IMG["Convert Page to PNG Image (pdf2image)"]
    
    PDF2IMG --> TESSERACT["Run Tesseract OCR (pytesseract)"]
    TESSERACT --> OCR_TEXT["OCR Page Text + Confidence Metadata"]
    
    PDF --> PLUMBER["pdfplumber Table Detector"]
    PLUMBER --> TABLES{"Grid Tables Found?"}
    TABLES -- Yes --> MARKDOWN_TABLE["Format Cells to Markdown Table Chunks"]
    TABLES -- No --> SKIP["Continue Normal Chunking"]
    
    PLAIN_TEXT --> CHUNKER["Sentence & Table Chunk Assembler"]
    OCR_TEXT --> CHUNKER
    MARKDOWN_TABLE --> CHUNKER
    
    CHUNKER --> INDEX["Vector Indexing"]
```

---

## Technical Metadata
- **OCR Engine**: Tesseract OCR (`pytesseract`).
- **Image Conversion**: `pdf2image` with poppler rendering.
- **Table Extractor**: `pdfplumber` bounding-box grid detection.
- **Table Metadata**: Chunks generated from tables store `table_id`, `row_count`, `col_count`, and `headers`.
