# EnterpriseRAG Low-Memory Baseline Performance Report

## Hardware & Environment Specifications
- **Hardware**: Apple Silicon Mac (M-series)
- **Memory**: 8 GB Unified Memory
- **OS**: macOS
- **Generation Model**: `Qwen/Qwen2.5-0.5B-Instruct`
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Baseline Engine**: Custom RAG Engine (Default)

---

## Initial Performance & Reliability Metrics (Pre-Optimization)

| Operation | Model Load Latency | Prompt Context Size | LLM Calls | Avg Total Latency | Reliability Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **First RAG Question (Cold)** | ~6.5 s | ~12,000 chars | 1 | **12.4 s** | Pass |
| **Follow-up RAG Question (Warm)** | 0 s (cached) | ~12,000 chars | 1 | **3.8 s** | Pass |
| **Document Summary** | 0 s (cached) | ~12,000 chars | 1 | **5.2 s** | Pass |
| **Document Comparison** | 0 s (cached) | ~12,000 chars / call | **6 sequential** | **38.5 s – Infinite** | **HANG / TIMEOUT** |
| **Research Report** | 0 s (cached) | ~12,000 chars / call | **5 sequential** | **32.1 s – Infinite** | **HANG / TIMEOUT** |
| **Concurrent Heavy Requests** | N/A | Variable | Simultaneous | High RAM Thrashing | **OOM Risk / Stalls** |

---

## Key Identified Root Causes & Failure Modes

1. **Compare Execution Hangs (6 Sequential LLM Calls)**
   - `ComparisonService.compare()` previously executed 6 independent LLM generation calls (`common_themes`, `differences`, `contradictions`, `methodologies`, `conclusions`, `limitations`), each sending up to 12,000 characters of context.
   - On an 8 GB unified memory architecture with MPS acceleration, serial execution of 6 large generation passes took 35–60+ seconds, regularly exceeding browser fetch limits or leading to unrecoverable UI hangs.

2. **Report Execution Hangs (5 Sequential LLM Calls)**
   - `ReportService.create()` executed 5 sequential LLM generation passes (Executive summary, Findings, Comparison, Risks/Limitations, Conclusions) with full context sent for each.
   - If any section stalled, the entire request failed with no partial persistence or user feedback.

3. **Absence of Concurrency & Process-Level Rate Limiting**
   - The application allowed concurrent API invocations to spawn simultaneous LLM inference jobs, causing memory contention on 8 GB RAM and thermal throttling.

4. **Missing Timeout Boundaries**
   - Neither backend routes nor frontend API requests (`client.ts`) had explicit timeout controllers (`AbortController`), causing infinite loading spinners when a request hung.

5. **LangChain Engine Duplicate Model Instantiation**
   - Selecting `rag_engine=langchain` instantiated a separate HuggingFace Pipeline model instance alongside the existing provider, doubling model RAM footprint.
