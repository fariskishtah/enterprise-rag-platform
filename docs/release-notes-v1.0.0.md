# EnterpriseRAG v1.0.0 Release Notes

**Release Date**: July 26, 2026  
**Version**: 1.0.0  
**Tag**: `v1.0.0`

---

## Portfolio & Hugging Face Spaces Launch

EnterpriseRAG v1.0.0 transforms the repository into a complete, recruiter-ready AI engineering portfolio product and Hugging Face Docker Space deployment.

### Key Highlights

1. **Multimodal Grounded Knowledge Intelligence**:
   - Ingestion and passage-level grounded QA across PDF, DOCX, TXT, scanned PDFs (OCR), structured grid tables, MP4/WAV media, and YouTube link ingestion.

2. **Dual RAG Engine Architecture**:
   - Production Custom Hybrid Engine (Dense MiniLM + BM25 Lexical + Reranker + Verification).
   - LangChain LCEL Engine featuring FAISS vector storage, composed runnable chains, and shared provider memory wrappers.

3. **Product Observability & Feedback**:
   - Evaluation Dashboard tracking correctness, faithfulness, citation accuracy, and median/P95 latency.
   - User Feedback System with rating analytics and 1-click conversion into evaluation benchmark test cases.

4. **Arabic & Multilingual Support**:
   - Modern Standard Arabic prompts, RTL interface rendering, and multilingual vector embeddings (`paraphrase-multilingual-MiniLM-L12-v2`).

5. **Low-Memory & Hugging Face Space Optimizations**:
   - Single-call Document Comparison (>80% latency reduction).
   - Process-level `GenerationQueue` semaphore restricting inference concurrency to eliminate OOM thrashing on 8 GB RAM.
   - Single-container multi-stage `Dockerfile` and `start-space.sh` with automated demo workspace seeding.
