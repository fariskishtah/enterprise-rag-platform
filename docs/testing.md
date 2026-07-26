# Testing

The backend suite uses real API calls with deterministic local embedding, generation,
PDF, WAV, ffmpeg, database, vector, and lifecycle behavior. It does not mock the RAG
or persistence pipeline.

`test_policy_e2e.py` validates the brief’s policy facts, citation contents, score
diagnostics, unknown CEO, knowledge-base scope, sentence duplication, and conversational
approval follow-up.

`test_media.py` validates local WAV upload, ffprobe/audio extraction, timestamps,
intelligence, transcript Q&A, timestamp citations, search, JSON export, retry idempotency,
duplicate rejection, private URL blocking, corrupt media, and no speech.

Vitest covers status semantics, timestamp citation links, and the critical research-chat
submission flow. Playwright runs the real FastAPI and Vite servers and covers document
RAG, local media, successful public-URL media import, exports, private-link error UX, and
desktop/tablet/mobile core actions.

`backend/scripts/evaluate_policy_rag.py` writes a human-readable Markdown table and full
JSON with expected/generated answers, passages, dense/lexical/reranking scores, citations,
support, pass/fail, and latency.

`backend/scripts/evaluate_real_models.py` runs the cached production MiniLM and Qwen
models through the same FastAPI surface and records answer quality, grounding, confidence,
citations, and stage latency in `artifacts/real-model-evaluation.{json,md}`.

`test_real_transcription.py` runs faster-whisper Tiny in CPU int8 mode against a local
spoken-audio fixture and refreshes `artifacts/real-transcription-result.json`. Tiny keeps
the validation lightweight; the application default remains faster-whisper Small.

Cold/warm model, retrieval, transcription, and frontend bundle measurements are collected
in `artifacts/performance-summary.md`.

The course suite is in `test_langchain_course_layer.py` and
`test_real_langchain_rag.py`. It directly covers imports, loaders, recursive splitting,
Hugging Face embedding wiring, FAISS persistence/deletion/reload, retrievers, prompt
rendering, Pydantic parsing, LCEL, the custom LangChain LLM adapter, generation controls,
model save/reload, quantization fallback, Streamlit import, and engine isolation.

Run the deterministic engine comparison with:

```bash
backend/.venv/bin/python backend/scripts/compare_rag_engines.py
```

The generated Markdown and JSON reports are
`artifacts/course-engine-comparison.{md,json}`.
