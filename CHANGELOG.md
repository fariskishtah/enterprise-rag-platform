# Changelog

All notable changes to EnterpriseRAG will be documented in this file.

## [v1.0.0] - 2026-07-26 — Portfolio & Hugging Face Spaces Release

### Added
- **Multimodal Grounded RAG**: Support for PDF, DOCX, TXT, scanned PDFs (OCR), tables, MP4/WAV media, and YouTube link ingestion.
- **Dual RAG Engine**: Custom hybrid dense + BM25 engine alongside LangChain LCEL engine.
- **Evaluation Dashboard**: Benchmark datasets, test execution, accuracy/faithfulness metrics, and CSV/JSON export.
- **User Feedback Pipeline**: Rating feedback analytics and 1-click conversion to evaluation test cases.
- **Arabic & Multilingual Support**: Arabic prompt engineering, RTL interface layout, and multilingual embeddings (`paraphrase-multilingual-MiniLM-L12-v2`).
- **Low-Memory Optimization**: Single-call Compare optimization (>80% latency reduction), process concurrency queueing, and runtime profiles (`low_memory`, `huggingface_demo`).
- **Hugging Face Space Deployment**: Multi-stage Dockerfile, `start-space.sh`, and automated demo dataset seeder.
- **Action Template Library**: 15+ pre-configured AI action templates for HR, contracts, study notes, and meeting minutes.
- **Local Auth Foundation**: JWT authentication, password hashing, and user-isolated resources.
- **Portfolio & Governance**: 20 automated screenshots, 15 architecture docs, 37-section case study, demo video script, and CI workflows.
