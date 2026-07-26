# Document Ingestion Architecture

The document ingestion pipeline processes uploaded files (PDF, DOCX, TXT) into chunked, embedded vector representations for search and retrieval.

---

## Document Ingestion Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as FastAPI Ingestion Endpoint
    participant Val as Validation Engine
    participant Ext as Extractor Registry
    participant OCR as Tesseract OCR Fallback
    participant Table as pdfplumber Table Extractor
    participant Chunk as Sentence Chunker
    participant Embed as Embedding Provider
    participant DB as SQLite Chunk Store

    User->>API: Upload PDF / DOCX / TXT
    API->>Val: Check SHA-256 Checksum & File Size
    Val-->>API: Validated
    API->>Ext: Route to Extractor (PdfExtractor / DocxExtractor)
    
    alt Text Extraction Successful
        Ext-->>API: Extracted Sections
    else Low Text Density (< 50 chars/page)
        Ext->>OCR: Trigger Page OCR Fallback
        OCR-->>Ext: OCR Text & Confidence
    end

    opt Structured Tables Found
        Ext->>Table: Extract Table Cells & Bounding Boxes
        Table-->>Ext: Table Markdown & Metadata
    end

    API->>Chunk: Chunk Text (size=800, overlap=120)
    Chunk-->>API: Document Chunks
    API->>Embed: Embed Chunks (MiniLM / Multilingual)
    Embed-->>API: Float32 Vectors
    API->>DB: Persist Chunks & Vectors
    DB-->>User: Status: ready_for_chat
```

---

## Key Extractor Modules

- **`PdfExtractor`**: Extracts pages using `pypdf`. Performs page-level text density check.
- **`DocxExtractor`**: Extracts paragraphs, headings, and docx tables.
- **`TxtExtractor`**: Paragraph-based UTF-8 text extraction.
- **`OcrEngine`**: Triggered automatically when pages are scanned images.
- **`TableExtractor`**: Formats grid structures into Markdown table blocks.
