# Engineering Case Study: EnterpriseRAG Platform

## 1. Problem Statement
Enterprise organization knowledge is fragmented across PDF contracts, scanned documents, spreadsheet tables, recorded meeting video, and internal training lectures. Standard generative AI solutions introduce hallucination risks, lack verifiable passage citations, and demand expensive external API subscriptions.

---

## 2. Product Vision
To build an end-to-end, local-first multimodal knowledge intelligence platform for low-resource containerized environments, with passage-level citations and video timestamp synchronization. Local file workflows do not require a hosted inference API; optional YouTube imports still depend on third-party availability.

---

## 3. Why RAG?
Retrieval-Augmented Generation (RAG) grounds language models by inserting retrieved passages directly into the prompt context. This can reduce unsupported answers and enables claim-support checks, but it does not eliminate model errors.

---

## 4. Initial Architecture
The initial architecture used a basic vector search pipeline (PyPDF text extraction + single dense vector retrieval + FLAN-T5 Small model).

---

## 5. Document-Processing Design
A modular extraction engine handles PDFs, DOCXs, and TXTs, converting documents into sentence-boundary chunks (`chunk_size=800`, `chunk_overlap=120`) with preserved metadata (page numbers, headings, section indices).

---

## 6. First Retrieval Failure
Single dense vector search failed on domain-specific product numbers, exact policy IDs, and proper nouns (e.g. searching "Clause 14.B" returned generic policy paragraphs instead of Clause 14.B).

---

## 7. Similarity Threshold Problems
Pure cosine similarity without thresholding retrieved low-relevance passages for out-of-domain questions, forcing the generative model to generate answers from irrelevant context. Setting a strict threshold prunes irrelevant candidates.

---

## 8. FLAN-T5 Small Limitations
FLAN-T5 Small (77M parameters) exhibited weak instruction following, frequently omitting structured formatting or truncating grounded responses.

---

## 9. Migration to Qwen
Migrated to `Qwen/Qwen2.5-0.5B-Instruct` (0.5B parameters), achieving superior instruction adherence, multi-sentence reasoning, and structured JSON output capabilities within a lightweight memory footprint (<1 GB VRAM).

---

## 10. Hybrid Retrieval
Engineered a hybrid retrieval system combining dense vector search (`sentence-transformers/all-MiniLM-L6-v2`) with lexical BM25 term matching.

---

## 11. Lexical Scoring
Integrated BM25-style term frequency scoring over normalized text tokens to improve exact-term retrieval for product codes, names, and numbers.

---

## 12. Reranking
Applied a score fusion algorithm:
$$\text{Score} = (0.45 \times \text{Dense}) + (0.30 \times \text{Lexical}) + (0.25 \times \text{Query Coverage})$$

---

## 13. Context Deduplication
Implemented a near-duplicate chunk filter (threshold 0.88) and per-document source capping (max 3 sources per document) to eliminate redundant context passages.

---

## 14. Citation Verification
Created a post-generation sentence-level claim verifier (`VerificationService`) that compares generated sentences against retrieved context, returning explicit claim support statuses (`fully_supported`, `partially_supported`, `unsupported`).

---

## 15. Explicit Insufficient-Evidence Behaviour
When retrieved passages fall below the similarity threshold or contain no relevant facts, the system explicitly returns `NOT_FOUND_ANSWER` ("The supplied documents do not contain enough information to answer"), avoiding guesswork.

---

## 16. Conversation-Aware Rewriting
Added a conversational query rewriter (`_resolve_session`) that converts follow-up questions ("What were its main risks?") into standalone search queries using past chat history.

---

## 17. LangChain Compatibility Layer
Implemented a parallel course-compatible RAG engine using LangChain, allowing users to switch between the custom hybrid engine and LangChain LCEL workflows via `RAG_ENGINE`.

---

## 18. FAISS Integration
Integrated FAISS vector store persistence (`LangChainEngineRuntime`) for fast vector similarity search in LangChain mode.

---

## 19. LCEL and PydanticOutputParser
Composed declarative LCEL chains (`QUERY_REWRITE_PROMPT | llm | PydanticOutputParser`) with automatic bounded repair retries for structured outputs.

---

## 20. Video and Audio Transcription
Integrated `faster-whisper` (`small` model, CPU `int8`) and official subtitle parsers to transcribe uploaded MP4/WAV media and public YouTube URLs into sentence-aligned transcripts.

---

## 21. Timestamp Citations
Coupled vector chunks generated from media with start/end timestamps. Clicking a citation in the React UI automatically triggers HTML5 video player seeking to that timestamp.

---

## 22. 8 GB Memory Constraints
Running local LLMs, embeddings, faster-whisper, and vector search on Apple Silicon Macs with 8 GB unified memory exposed memory pressure and thermal throttling risks under parallel load.

---

## 23. Compare Hanging
`ComparisonService.compare()` originally executed **6 sequential LLM generation calls** (one for each analysis dimension), taking 35–60+ seconds and triggering browser network timeouts.

---

## 24. Report Hanging
`ReportService.create()` executed **5 sequential LLM calls** with full context, causing unrecoverable hangs if any section stalled.

---

## 25. Reducing Compare from Six Model Calls to One
Re-engineered `ComparisonService.compare()` to use a **single consolidated LLM prompt** with regex section extraction, reducing comparison latency from 38.5s+ to **4.2s** (>80% reduction).

---

## 26. Shared Model Provider
Configured `LangChainEngineRuntime` (`langchain_force_wrapper=True`) to wrap the existing model provider in memory, eliminating duplicate model weight instantiation.

---

## 27. Generation Semaphore
Implemented a bounded process-wide generation queue, serializing heavy model work to reduce memory-pressure and OOM risk on constrained hosts.

---

## 28. Timeouts
Wrapped all route endpoints with `asyncio.wait_for` timeouts returning standard HTTP 504 `GenerationTimeoutError`.

---

## 29. AbortController
Configured the frontend `client.ts` fetch wrapper with an `AbortController` (30s default / 150s intelligence), replacing infinite spinners with actionable error notices.

---

## 30. Low-Memory Runtime Profile
Created `APP_RUNTIME_PROFILE=low_memory` to automatically enforce 4,000 character context windows, 128 max new tokens, and single-concurrency execution.

---

## 31. Testing Methodology
Built a multi-tier test architecture with backend unit/integration tests, Playwright browser tests, frontend unit tests, and Ruff linting. Current counts are recorded in the release documentation rather than frozen in this historical narrative.

---

## 32. Evaluation Methodology
Implemented an empirical Evaluation System (`EvaluationService`) calculating correctness, faithfulness, citation validity, and median/P95 latency across benchmark test datasets.

---

## 33. Security Controls
Enforced untrusted-context markers, SSRF URL validation, bcrypt password hashing, signed expiring session cookies, bounded login attempts, upload validation, and public-demo quotas. The shared demo is not presented as a multi-tenant authorization boundary.

---

## 34. Results & Metrics

### Historical development observations

The figures below were recorded during earlier local development runs, not under the current
public-release test protocol. They are retained as engineering notes and must not be read as
repeatable benchmarks, cloud results, or production guarantees.

| Operation | Pre-Optimization Latency | Post-Optimization Latency | Change |
| :--- | :--- | :--- | :--- |
| **Document Comparison** | 38.5s – Infinite (Hangs) | **4.2s – 7.8s** | **>80% Faster** |
| **Research Report** | 32.1s – Infinite (Hangs) | **8.5s – 14.2s** | **>60% Faster** |
| **Follow-up RAG Query** | 3.8s | **2.1s – 3.2s** | **25% Faster** |
| **Memory Footprint (RAM)** | Swap Thrashing / OOM | **<2.5 GB observed in the cited run** | **No OOM observed in that run** |

### Custom Engine vs. LangChain Engine Trade-Offs

| Metric / Aspect | Custom Hybrid Engine | LangChain LCEL Engine |
| :--- | :--- | :--- |
| **Retrieval Strategy** | Hybrid (Dense + BM25 + Reranker) | FAISS Dense Vector Search |
| **Latency (Warm)** | **2.1s** | **2.8s** |
| **Memory Overhead** | Minimal (Relational Float32) | FAISS Index Memory Footprint |
| **Course Alignment** | High (Custom architecture) | High (Direct LCEL runnable chains) |

### Runtime Profile Configurations

| Parameter | `low_memory` Profile | `balanced` Profile | `quality` Profile |
| :--- | :--- | :--- | :--- |
| **Max Concurrent Generations** | 1 (Serialized) | 2 | 4 |
| **Context Window (chars)** | 4,000 | 12,000 | 24,000 |
| **Max New Tokens** | 128 | 256 | 512 |
| **Generation Timeout** | 45s | 90s | 180s |

---

## 35. Limitations
- **Tesseract CPU Speed**: Scanned PDF OCR takes ~2–4s per page on CPU.
- **Context Length**: 0.5B parameter models perform best when context remains under 4,000 characters.

---

## 36. Lessons Learned
1. Consolidating multi-prompt workflows into a single structured prompt yields massive performance gains on local hardware.
2. Hard process-level semaphores are essential for preventing memory thrashing on 8 GB devices.
3. Explicit evidence and verification gates make unsupported output more visible than prompt tuning alone, but cannot guarantee correctness.

---

## 37. Future Roadmap
- Multi-tenant organization workspace support.
- Server-Sent Events (SSE) streaming response support for real-time token rendering.
