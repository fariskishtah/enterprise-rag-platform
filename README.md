# EnterpriseRAG

EnterpriseRAG is a local-first AI Knowledge Intelligence Platform. It turns private
documents, recordings, and accessible public videos into concise grounded answers,
timestamped transcripts, evidence-backed summaries, comparisons, and reports.

The trust model is simple: every answer is scoped to an explicit knowledge base, every
claim is checked against an individual passage, and citations open the source page or
transcript timestamp. Uploaded content is treated as untrusted data and cannot instruct
the assistant or override grounding rules.

No OpenAI, Anthropic, or paid model endpoint is required.

## Product capabilities

- PDF, UTF-8 TXT, and DOCX upload, extraction, deterministic chunking, embedding, and
  indexing.
- MP4, MOV, MKV, WEBM, M4A, MP3, and WAV upload with ffprobe validation.
- Public HTTP(S) and YouTube link ingestion with SSRF protection and no access-control
  bypass.
- Official/automatic subtitle import when accessible, followed by local Whisper
  transcription when subtitles are unavailable.
- Timestamped transcript, search, player synchronization, chapters, short and detailed
  summaries, key points, decisions, action items, entities, lecture aids, meeting aids,
  and TXT/Markdown/JSON exports.
- Hybrid dense and BM25-style retrieval, score fusion, direct-relevance reranking,
  near-duplicate removal, source diversity, and bounded context.
- Concise grounded answers, conversation-aware follow-ups, used-passage citations,
  confidence, claim support, and developer evidence.
- Summary, multi-source comparison, and research-report workflows.
- Responsive cinematic React workspace with light/dark themes, command palette, source
  intake, research chat, document inspection, and video intelligence.

## Architecture

```text
React 19 + strict TypeScript
        │
        ▼
FastAPI / Pydantic API
        │
        ├── document pipeline
        │     extraction → sentence-safe chunks → embeddings → vectors
        │
        ├── media pipeline
        │     validate → subtitles/audio → Whisper → timestamp chunks
        │     → vectors → media intelligence
        │
        ├── grounded RAG
        │     rewrite → dense candidates → lexical fusion → rerank/deduplicate
        │     → support gate → local generation → post-process → claim verification
        │
        └── SQLAlchemy repositories → SQLite + local filesystem
```

Vectors use durable float32 storage in the relational chunk table and local cosine
search. The adapter boundary permits pgvector, FAISS, or another production vector store
without changing routes or product pages. See [architecture](docs/architecture.md).

## Models

| Job | Default | Rationale |
| --- | --- | --- |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Strong small CPU embedding model |
| Generation | `Qwen/Qwen2.5-0.5B-Instruct` | Better instruction following than FLAN-T5 Small at practical local size |
| Generation fallback | `google/flan-t5-base`, then extractive local fallback | Graceful offline or memory-constrained behavior |
| Transcription | faster-whisper `small`, CPU `int8` | Practical accuracy/latency balance; GPU is configurable |

Models load lazily and cache under `backend/data/models`. Completely offline operation is
available after caching by setting `ENTERPRISE_RAG_HF_LOCAL_FILES_ONLY=true`.
Device selection defaults to `auto` (CUDA, then Apple MPS, then CPU). Quantized int8
generation can be enabled on supported CUDA accelerators. See [model notes](docs/models.md).

## Hardware expectations

- Python 3.11+ (validated here on Python 3.14)
- Node.js 20+ and npm 10+
- ffmpeg and ffprobe on `PATH`
- 4 GB RAM minimum for deterministic/test providers
- 8 GB RAM recommended for MiniLM + Qwen 0.5B + Whisper Small
- Several GB of free disk space for local model caches
- CPU works. Apple Silicon MPS and CUDA accelerate embeddings and generation; faster-whisper
  uses CPU or CUDA.

## Install

```bash
cd /Users/fariskishtah/Desktop/EnterpriseRAG

python3 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[dev,media]'

cd frontend
npm install
npx playwright install chromium
```

Copy `.env.example` to `backend/.env` only when changing defaults.

Install the optional course demonstrations with:

```bash
backend/.venv/bin/pip install -e 'backend[dev,media,course]'
```

## Migrations

```bash
cd /Users/fariskishtah/Desktop/EnterpriseRAG/backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

The current head is `0003_media_intelligence`. The migration is reversible to
`0002_rag` for validation, which removes only the new media tables. Normal upgrade keeps
existing document, chunk, vector, and conversation data.

If a development application ran `Base.metadata.create_all` before its Alembic revision
was updated, inspect the schema and only stamp the matching revision when it is truly
identical. Never stamp a mismatched database.

## Run

Backend:

```bash
cd /Users/fariskishtah/Desktop/EnterpriseRAG/backend
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd /Users/fariskishtah/Desktop/EnterpriseRAG/frontend
npm run dev
```

Open <http://localhost:5173>. OpenAPI documentation is at
<http://localhost:8000/docs>.

## Dual RAG engines

The custom engine remains the default and primary product architecture:

```bash
RAG_ENGINE=custom backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```

The course engine preserves the same API surface while adding direct LangChain loaders,
splitters, Hugging Face integrations, persistent FAISS retrieval, LCEL, and Pydantic
output parsing:

```bash
RAG_ENGINE=langchain backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```

Reprocess documents after changing an existing knowledge base from `custom` to
`langchain` so its per-knowledge-base FAISS index is created. Indexes persist beneath
`backend/data/langchain_indexes` by default and reload across application restarts.

## Course Technology Coverage

The custom column means the existing product path. The course column means direct use of
the requested library rather than a custom equivalent.

| Course concept | Exact library/class | Implementation | Notebook | Status |
| --- | --- | --- | --- | --- |
| LangChain packages | `langchain`, `langchain-core`, `langchain-community` | `backend/pyproject.toml` | All LangChain notebooks | Course engine |
| Document loaders | `PyPDFLoader`, `TextLoader`, `Docx2txtLoader` | `backend/app/ai/langchain_engine/document_pipeline.py` | `langchain_rag_demo.ipynb` | Course engine + tests |
| Text splitting | `RecursiveCharacterTextSplitter` | `backend/app/ai/langchain_engine/document_pipeline.py` | `langchain_rag_demo.ipynb` | Course engine + tests |
| Embeddings | `langchain_huggingface.HuggingFaceEmbeddings` | `backend/app/ai/langchain_engine/document_pipeline.py` | `langchain_rag_demo.ipynb` | Course engine + real test |
| Vector store/retriever | `FAISS`, `BaseRetriever` | `backend/app/ai/langchain_engine/document_pipeline.py` | `langchain_rag_demo.ipynb` | Persistent course engine |
| Prompt templates | `PromptTemplate` | `backend/app/ai/langchain_engine/prompts.py` | `langchain_chains_and_parser.ipynb` | Six course templates |
| Structured parsing | `PydanticOutputParser` | `backend/app/ai/langchain_engine/chains.py` | `langchain_chains_and_parser.ipynb` | Course engine + repair |
| LCEL | `RunnableLambda`, `RunnablePassthrough`, `prompt \| llm \| parser` | `backend/app/ai/langchain_engine/chains.py` | `langchain_chains_and_parser.ipynb` | Composed course engine |
| Custom LangChain LLM | `langchain_core.language_models.llms.LLM` | `backend/app/ai/langchain_engine/llm.py` | `huggingface_pipeline_demo.ipynb` | Adapter + tests |
| HF pipeline | `transformers.pipeline`, `HuggingFacePipeline` | `backend/app/ai/langchain_engine/llm.py` | `huggingface_pipeline_demo.ipynb` | Course engine/demo |
| Generation controls | `temperature`, generation `top_k`, `top_p`, `max_new_tokens`, repetition penalty, sampling | `backend/app/core/config.py` | Pipeline/Streamlit notebooks | Both engines |
| Quantization | `BitsAndBytesConfig` 4-bit/8-bit | `backend/app/ai/quantization.py` | `quantization_bitsandbytes.ipynb` | CUDA optional |
| Model save/reload | `save_pretrained`, `from_pretrained`, `local_files_only` | `backend/app/ai/model_io.py` | `model_save_reload.ipynb` | Utility + tests |
| PEFT/LoRA | `LoraConfig`, `get_peft_model`, `PeftModel` | `course_demo/fine_tuning/train_lora.py` | `lora_fine_tuning.ipynb` | Optional education |
| Streamlit | `streamlit` | `course_demo/streamlit_app/app.py` | `streamlit_ngrok_demo.ipynb` | Separate demo |
| ngrok | `pyngrok` | `course_demo/ngrok/launch_tunnel.py` | `streamlit_ngrok_demo.ipynb` | Explicit opt-in |
| Engine evaluation | Custom API vs LangChain FAISS/LCEL | `backend/scripts/compare_rag_engines.py` | — | Deterministic report |

Detailed architecture, API behavior, hardware limits, exact commands, and the comparison
between `model.generate()`, `pipeline()`, and `HuggingFacePipeline` are in
[Course compatibility](docs/course-compatibility.md).

## Document RAG flow

```text
upload → validate → extract pages/sections → sentence-safe chunks
→ embeddings → vector index → hybrid retrieval → rerank → grounded answer
→ used-source citations → claim verification
```

The answer prompt requires a direct answer first, one or two sentences for factual
questions, short lists and comparisons, no repeated chunks, no irrelevant copying, and
an explicit not-found response. Post-processing removes duplicated sentences, bounds
length by question type, rejects long copied passages, validates citation support, and
downgrades unsupported claims.

## Video flow

```text
uploaded_or_linked → validating → fetching_metadata
→ downloading_or_extracting_subtitles → extracting_audio → transcribing
→ transcript_ready → chunking → embedding → indexing → summarising → ready
```

Every failure stores its stage, stable error code, safe user message, bounded technical
message, retryability, and timestamp. Retries replace deterministic segments, transcript
chunks, vectors, chapters, and summaries rather than duplicating them.

For public URLs EnterpriseRAG:

- allows only HTTP(S);
- blocks credentials, localhost, private, link-local, reserved, multicast, and unspecified
  addresses;
- revalidates redirects;
- enforces download/duration/time limits;
- invokes yt-dlp/ffmpeg without a shell;
- does not bypass DRM, authentication, paywalls, private videos, or platform controls;
- removes per-attempt temporary files.

## API groups

- `/api/v1/knowledge-bases`
- `/api/v1/knowledge-bases/{id}/documents`
- `/api/v1/documents/{id}/process|retry|extraction|preview|chunks`
- `/api/v1/knowledge-bases/{id}/ask|retrieve`
- `/api/v1/chat-sessions`
- `/api/v1/intelligence/summaries|comparisons|reports`
- `/api/v1/knowledge-bases/{id}/media`
- `/api/v1/knowledge-bases/{id}/media/from-url`
- `/api/v1/media/{id}/process|retry|transcript|intelligence|ask|export`
- `/api/v1/rag/config`

See [API notes](docs/api.md).

## Quality and tests

```bash
cd /Users/fariskishtah/Desktop/EnterpriseRAG

backend/.venv/bin/ruff format --check backend/app backend/tests backend/migrations backend/scripts
backend/.venv/bin/ruff check backend/app backend/tests backend/migrations backend/scripts
backend/.venv/bin/pytest -q backend/tests

PYTHONPATH=backend backend/.venv/bin/python backend/scripts/evaluate_policy_rag.py
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/evaluate_real_models.py

cd frontend
npm run typecheck
npm run test
npm run build
npm run test:e2e
npm audit
```

The deterministic policy PDF covers remote days, collaboration days, the 120-kilometre
rule, required approvals, home-office allowance, learning budget, an unknown CEO, and a
conversational approval follow-up. The report is written to
`artifacts/policy-rag-evaluation.{json,md}`.

Browser tests exercise real document upload, citations, follow-up and unknown answers,
local media upload, a successful public-URL import, transcription, exact timestamp
citations, summaries, scoped Q&A, export, private-URL errors, and desktop/tablet/mobile
usability. Screenshots and the HTML report live under `artifacts/`.

Real model checks are opt-in because first runs download model weights:

```bash
RUN_REAL_MODEL_TESTS=1 backend/.venv/bin/pytest -q backend/tests/test_real_huggingface_rag.py
RUN_REAL_TRANSCRIPTION_TESTS=1 backend/.venv/bin/pytest -q backend/tests/test_real_transcription.py
```

See [testing](docs/testing.md).

## Privacy and security

- Source files, vectors, transcripts, model weights, and chat history remain local.
- Stored filenames are generated from UUIDs, never user path input.
- Upload type/size, media stream, duration, URL, DNS address, redirect, and timeout checks
  run before processing.
- Uploaded text is untrusted prompt data. Embedded instructions cannot override grounding.
- React renders escaped text and does not inject source HTML.
- Logs and explainability return model/timing/score data, not secrets or tokens.
- Citation validation checks the individual cited passage, numbers, and negation.

This local profile has no authentication or tenant isolation. Do not expose it directly
to an untrusted network. See [deployment](docs/deployment.md).

## Known limitations

- Local relational vector search scans in process and should be replaced for large corpora.
- Background tasks are in-process; production needs a durable queue and distributed locks.
- Scanned PDFs require an OCR adapter.
- Subtitle/video access depends on the public source and platform policy.
- Whisper Tiny is fast but may mishear names; the default Small model is more accurate.
- Local compact generators can still be imperfect; unsupported output is downgraded or
  returned as not found, but human review remains appropriate for high-stakes decisions.
- Entity, action-item, and educational extraction is transparent/local and intentionally
  conservative rather than a full enterprise NLP ontology.

## Deployment roadmap

1. OIDC/SAML authentication, RBAC, workspaces, and tenant isolation.
2. Durable object storage, task queue, cancellation, and worker autoscaling.
3. pgvector/FAISS with tenant-aware indexes and retrieval telemetry.
4. OCR, table/image understanding, and multilingual evaluation sets.
5. Signed source URLs, audit logs, retention controls, and deployment secrets manager.
6. Container/Kubernetes profiles with CPU and GPU worker pools.
