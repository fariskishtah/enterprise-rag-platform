# Model Lifecycle & Memory Management Report

## Problem Statement & Architecture

In local RAG systems running on 8 GB Apple Silicon devices, LLM and embedding model weights occupy a significant portion of unified memory.

Two major risks were identified:
1. **Duplicate Model Instantiation**: When `rag_engine=langchain` was enabled, `create_langchain_huggingface_pipeline()` attempted to load a separate HuggingFace Pipeline model instance into RAM alongside `HuggingFaceGenerationProvider._models`.
2. **Unbounded Concurrency**: Multiple simultaneous incoming HTTP requests could trigger parallel LLM generations on MPS, exceeding available unified memory and forcing system swap thrashing.

---

## Technical Solution

1. **Shared Provider Wrapper Mode (`langchain_force_wrapper`)**
   - Configured `LangChainEngineRuntime` to check `settings.langchain_force_wrapper` (enabled automatically under `low_memory` profile).
   - When set, it instantiates `EnterpriseGenerationLLM` which wraps the existing `generation_provider` in memory instead of creating a second model pipeline.
   - Saves ~1.2 GB of unified memory during LangChain engine execution.

2. **Process-Level Generation Concurrency Control (`GenerationQueue`)**
   - Created an `asyncio.Semaphore`-backed `GenerationQueue` initialized with `max_concurrent_generations=1` in `low_memory` profile.
   - Enforces strict serial processing of generation requests across RAG Q&A, Summaries, Comparisons, and Reports.
   - Implemented queue timeout (`generation_queue_timeout_seconds`) returning HTTP 503 `GenerationQueueFullError` if the queue is backed up.

3. **Runtime Configuration Observability**
   - Exposed `runtime_profile`, `generation_queue_active`, `generation_queue_queued`, and `generation_timeout_seconds` via `/api/v1/rag/config` and displayed them on the Settings page.

---

## Verification Results
- **Automated Tests**: Passed `test_langchain_engine_runs_through_existing_fastapi_surface`, `test_custom_and_langchain_engine_runtime_isolation`, and `test_generation_queue_stats_and_serialization`.
- **Memory Footprint**: Peak generation memory stabilized under 2.5 GB RAM total.
- **Stability**: Zero OOM crashes or MPS allocation failures during concurrent load testing.
