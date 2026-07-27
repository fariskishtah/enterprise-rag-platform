# 00 — Project overview

## What EnterpriseRAG is

EnterpriseRAG is a local-first knowledge application. A user creates a knowledge base, adds documents or media, and asks questions about those sources. The backend extracts text, splits it into smaller chunks, creates numeric embeddings, retrieves relevant chunks, and asks a local Hugging Face model to answer from that evidence. Answers include citations and a verification result. The product also supports document summaries, comparisons, research reports, media transcripts, evaluation runs, and operational maintenance.

The product entry point is `backend/app/main.py:create_app` at lines 52-226. It builds the FastAPI application, database connection, file storage, model providers, request middleware, API router, and production static-file fallback. The React route selection is in `frontend/src/App.tsx:110-164`.

The core problem is trust: a normal chatbot can answer from general training data without showing its evidence. EnterpriseRAG tries to answer only from sources in a selected knowledge base, show the passages it used, and say when support is weak. The grounded request path is implemented by `RagService` in `backend/app/services/rag.py:97`, retrieval in `backend/app/services/retrieval.py:18`, reranking in `backend/app/services/reranking.py:73`, and verification in `backend/app/services/verification.py:50`.

Likely users are analysts, researchers, students, policy teams, HR teams, contract reviewers, and meeting owners who want private, source-linked answers. This describes the workflows in the code; a real customer profile or production usage history is **Not verified from the current codebase.**

## Main workflows

1. **Enter the product.** Public routes show the landing, login, and legal pages. Other routes call `/api/v1/auth/session` before showing the application shell (`frontend/src/App.tsx:64-107`).
2. **Create a knowledge base.** The user creates a named collection through `KnowledgeBasesPage` and `POST /api/v1/knowledge-bases` (`frontend/src/pages/KnowledgeBasesPage.tsx:7-48`; `backend/app/api/routes/knowledge_bases.py:32-53`).
3. **Add a source.** The source library accepts PDF, TXT, DOCX, common audio/video files, or a public media URL (`frontend/src/pages/UploadPage.tsx:63-262`).
4. **Process documents.** The backend validates, extracts, chunks, embeds, and indexes a document in `DocumentProcessingService` (`backend/app/services/processing.py:26`).
5. **Process media.** The backend validates a direct upload or URL, prefers subtitles, otherwise extracts audio and uses faster-whisper, then creates transcript-backed chunks (`backend/app/services/media.py:268` and `:418`; `backend/app/media/transcription.py:46`).
6. **Ask and inspect evidence.** The chat calls `POST /knowledge-bases/{id}/ask`; the backend rewrites the query, retrieves/reranks chunks, generates an answer, verifies it, and stores the conversation (`backend/app/api/routes/rag.py:50-115`; `backend/app/services/rag.py:97`).
7. **Analyze or evaluate.** Users can generate summaries/comparisons/reports, or run an existing evaluation dataset (`backend/app/api/routes/intelligence.py:36-113`; `backend/app/api/routes/evaluation.py:71-189`).
8. **Operate the demo.** Health/readiness, model warmup, expiry cleanup, backup, restore, and deployment scripts support a small public host (`backend/app/api/routes/health.py`; `backend/app/services/cleanup.py:59`; `scripts/`).

## How the parts work together

```text
Browser
  -> React pages and API client
  -> same-origin /api/v1 request
  -> FastAPI middleware and route handler
  -> service and repository
  -> SQLite records + uploaded files + model/index cache
  -> local embedding/generation/transcription model
  -> JSON response
  -> React state, citations, progress, or an actionable error
```

- **Frontend:** React renders the interface. It uses a small manual pathname router rather than React Router (`frontend/src/App.tsx:110-164`). `frontend/src/api/client.ts:27-147` adds the `/api/v1` prefix, a stored bearer token when present, same-origin cookies, request timeouts, and common error handling.
- **Backend:** FastAPI defines the HTTP interface. `backend/app/api/router.py:17-28` includes 11 route modules. Services contain processing and AI logic; repositories contain common database queries.
- **Database:** SQLAlchemy maps 19 tables and SQLite is the default (`backend/app/core/config.py:46`). Alembic tracks four revisions, but a fresh migration-only database currently lacks six ORM tables that application startup later creates with `Base.metadata.create_all`; this reproducibility gap is documented in the database and risk guides.
- **File storage:** `LocalFileStorage` writes uploads below a configured root and prevents paths from escaping it (`backend/app/services/storage.py:20`). Extracted text and embeddings are stored in SQLite; original/derived files live in storage.
- **Models:** sentence-transformers creates embeddings; Transformers supplies local answer generation; faster-whisper transcribes when no usable subtitle exists. Model providers are wired at `backend/app/main.py:142-180`.
- **Optional LangChain engine:** selecting `rag_engine=langchain` creates a persistent FAISS pipeline and LCEL chains (`backend/app/main.py:160-171`; `backend/app/ai/langchain_engine/`). The custom engine remains the default (`backend/app/core/config.py:75-78`).
- **Production packaging:** a multi-stage Docker build compiles React, installs Deno and Python/media dependencies, and copies the static bundle into FastAPI (`Dockerfile:5-70`). Nginx proxies public traffic to the loopback-only container port (`deploy/nginx/enterprise-rag.conf.template:15-60`).

## Technology map

| Technology | Where and why it is used | Important evidence | How to verify |
|---|---|---|---|
| React 19 | Builds the browser UI and page state. | `frontend/package.json:15-19`; `frontend/src/App.tsx` | `npm run build --prefix frontend` and open `/`. |
| TypeScript | Adds compile-time checking to frontend code. | `frontend/package.json:8-10,28`; `frontend/tsconfig.json` | `npm run typecheck --prefix frontend`. |
| Vite | Development server and production bundle builder. | `frontend/package.json:7-10,29` | `npm run build --prefix frontend`; inspect `frontend/dist/`. |
| Vitest + Testing Library | Deterministic component and API-client tests. | `frontend/package.json:21-30`; `frontend/src/**/*.test.*` | `npm run test --prefix frontend`. |
| Playwright | Browser navigation and production smoke tests. | `frontend/e2e/*.spec.ts`; `frontend/playwright.config.ts` | `npm run test:e2e --prefix frontend`. |
| FastAPI | Defines the API, validation, middleware, and static SPA server. | `backend/app/main.py:52-226`; `backend/app/api/router.py` | `curl http://127.0.0.1:7860/api/v1/health`. |
| Pydantic | Validates settings and request/response schemas. | `backend/app/core/config.py:15-292`; `backend/app/schemas/` | Start the app with an invalid bounded setting and observe startup validation. |
| SQLAlchemy | Maps Python models to relational tables and runs queries. | `backend/app/models/`; `backend/app/db/session.py` | Run backend tests or inspect SQLite safely as described in the database guide. |
| Alembic | Applies the tracked schema revisions; the current chain has a documented six-table coverage gap. | `backend/migrations/versions/`; `backend/alembic.ini`; `backend/app/main.py:66-72` | Upgrade a disposable database, compare its tables with `Base.metadata.tables`, and run the application tests. |
| SQLite | Default local/production-demo relational database. | `backend/app/core/config.py:46`; `.env.aws-cpu.example` | Query `sqlite_master` read-only. |
| sentence-transformers | Loads the embedding model and creates normalized vectors. | `backend/app/ai/providers/huggingface.py:16-154` | Run opted-in real-model tests after models are available. |
| Transformers + PyTorch | Loads and runs the local generation model. | `backend/app/ai/providers/huggingface.py:156`; `backend/app/ai/quantization.py` | Warm models through `/api/v1/rag/warmup`, then inspect `/rag/config`. |
| Custom relational vector store | Stores float32 embeddings in `document_chunks` and performs local similarity search. | `backend/app/ai/vectorstores/relational.py:13`; `backend/app/models/document.py:132-158` | Process a source, then call `/knowledge-bases/{id}/retrieve`. |
| LangChain + FAISS | Optional alternate RAG engine and direct course-technology path. | `backend/pyproject.toml:17-21`; `backend/app/ai/langchain_engine/` | Set the LangChain engine, reprocess, and run LangChain tests. |
| pypdf/pdfplumber/pdf2image/Tesseract | PDF text, tables, page images, and OCR fallback. | `backend/app/document_processing/extraction.py:96`; `backend/app/document_processing/tables.py`; `backend/app/document_processing/ocr.py` | Process text PDF, table PDF, and scanned PDF fixtures. |
| python-docx/docx2txt | Reads DOCX files in the custom and LangChain paths. | `backend/pyproject.toml:13,31`; `backend/app/document_processing/extraction.py:209` | Upload a small valid DOCX. |
| ffmpeg/ffprobe | Validates media, extracts audio, and supports download/transcription. | `Dockerfile:23-32`; `backend/app/services/media.py:418` | `docker run ... ffmpeg -version` and process an MP3/MP4. |
| faster-whisper | CPU transcription when subtitles are unavailable. | `backend/pyproject.toml:47-49`; `backend/app/media/transcription.py:46` | Run opted-in real transcription tests with a cached model. |
| yt-dlp + Deno | Fetches allowed public media/subtitles and solves supported YouTube JavaScript challenges. | `backend/pyproject.toml:38`; `Dockerfile:13-21`; `backend/app/services/media.py:170-266` | In the container run `deno --version` and a safe `yt-dlp --skip-download` check. |
| Nginx | Public reverse proxy, size/time limits, security headers, and asset caching. | `deploy/nginx/enterprise-rag.conf.template` | `nginx -t`, then request `/`, `/assets/...`, and `/api/v1/health`. |
| Docker Compose | Runs one constrained app container with persistent data/model volumes and a read-only cookie mount. | `docker-compose.aws.yml:1-47` | `docker compose -f docker-compose.aws.yml config --quiet`. |
| systemd | Starts Compose and schedules cleanup and backups on AWS. | `deploy/systemd/` | `systemctl list-timers` and service status on the host. |
| Bash backup/deploy scripts | Verified backups, safe restore, health-gated deploy, and rollback. | `scripts/backup-production.sh`; `restore-production.sh`; `deploy-aws.sh` | Use dry-run/verification steps in the testing and deployment guides. |
| Streamlit, ngrok, PEFT/LoRA | Separate learning demonstrations, not production UI/runtime. | `course_demo/streamlit_app/`; `course_demo/ngrok/`; `course_demo/fine_tuning/` | Run only the explicit course commands; they are not started by FastAPI. |

## Direct product versus learning demonstrations

The production React/FastAPI product directly supports both custom and LangChain RAG paths. Streamlit and ngrok are not alternate production entry points: they are explicit demonstrations in `course_demo/`. LoRA fine-tuning is also an experimental course script using a small synthetic example; the product does not fine-tune user uploads. Model bundle save/reload helpers exist in `backend/app/ai/model_io.py:8-55`, but normal production startup loads configured Hugging Face model IDs or local caches instead of calling those helpers.

## Data and privacy summary

Uploaded files, extracted text, transcripts, questions, model answers, citations, and evaluation/feedback records can be stored on the server. The legal page states that public-demo users must not upload sensitive data (`frontend/src/pages/LegalPage.tsx:9-25`). Lifecycle fields allow demo records to expire (`backend/app/db/base.py:24-31`), and an hourly systemd timer runs cleanup (`deploy/systemd/enterprise-rag-cleanup.timer:4-8`). This is not a guarantee of compliance with a specific privacy standard. Compliance certification is **Not verified from the current codebase.**
