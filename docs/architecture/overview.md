# EnterpriseRAG System Architecture Overview

EnterpriseRAG is an end-to-end multimodal AI platform designed for local-first, evidence-aware knowledge intelligence across documents, media, and public web sources. Retrieval, citations, and claim-support checks reduce unsupported output but do not guarantee correctness.

---

## High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Sources ["Ingestion Sources"]
        PDF["PDF / DOCX / TXT Documents"]
        OCR_DOCS["Scanned PDFs (OCR)"]
        MEDIA["MP4 / MOV / WAV Audio & Video"]
        URLS["YouTube & Public URLs"]
    end

    subgraph Pipeline ["Processing & Indexing Pipeline"]
        VAL["Validation & SHA-256 Checksum"]
        EXT["Extraction & Table Parsing"]
        OCR_FALLBACK["OCR Fallback (Tesseract)"]
        TRANSCR["Whisper Transcription & Subtitles"]
        CHUNK["Sentence-Boundary Chunking"]
        EMBED["Vector Embedding (MiniLM / Multilingual)"]
        INDEX["Vector Indexing (Relational Float32 / FAISS)"]
    end

    subgraph Retrieval ["Hybrid Retrieval & Grounding"]
        REWRITE["Query Rewriting"]
        DENSE["Dense Cosine Search (0.45)"]
        LEXICAL["BM25 Lexical Fusion (0.30)"]
        RERANK["Direct Relevance Reranker (0.25)"]
        QUEUE["Process Semaphore Queue (max=1 on 8GB)"]
        LLM["Local Generation (Qwen2.5-0.5B / Custom / LangChain)"]
        VERIFY["Sentence Claim Verification"]
    end

    subgraph Output ["Client & Interfaces"]
        REACT["React 19 Frontend (RTL / Light / Dark)"]
        CITATIONS["Passage & Video Timestamp Citations"]
        EVAL["Evaluation & Feedback Analytics"]
    end

    PDF --> VAL
    OCR_DOCS --> VAL
    MEDIA --> VAL
    URLS --> VAL

    VAL --> EXT
    EXT -- "Low text density" --> OCR_FALLBACK
    EXT --> CHUNK
    OCR_FALLBACK --> CHUNK
    VAL --> TRANSCR --> CHUNK

    CHUNK --> EMBED --> INDEX
    INDEX --> DENSE
    REWRITE --> DENSE
    REWRITE --> LEXICAL

    DENSE --> RERANK
    LEXICAL --> RERANK
    RERANK --> QUEUE --> LLM --> VERIFY --> CITATIONS --> REACT
    VERIFY --> EVAL
```

---

## Core Component Summary

| Layer | Technology | Primary Function |
| :--- | :--- | :--- |
| **API Layer** | FastAPI 0.115 / Pydantic v2 | REST API, async route handling, timeout middleware |
| **Document Processing** | PyPDF, pdfplumber, pytesseract, docx | Multi-format document, OCR, and table extraction |
| **Media Processing** | faster-whisper, ffmpeg, yt-dlp | Video transcription, audio extraction, timestamp alignment |
| **Embeddings** | Sentence-Transformers | 384d MiniLM / Multilingual vector embedding generation |
| **Vector Storage** | SQLite Float32 Chunks / FAISS | Local persistent vector storage and cosine distance search |
| **Generative LLM** | Qwen2.5-0.5B-Instruct / FLAN-T5 | Local grounded answer, summary, compare, report generation |
| **Frontend UI** | React 19 + TypeScript | Dynamic interactive workspace, citations, RTL, Light/Dark theme |
