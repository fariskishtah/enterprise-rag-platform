# 03 — File map

Paths are relative to the repository root.

## Frontend entry, routing, and types

| File | Responsibility |
|---|---|
| `frontend/src/main.tsx` | Mounts React and the top-level error boundary into the browser document. |
| `frontend/src/App.tsx` | Lazy-loads all pages, manually matches the pathname, marks public routes, and protects all other routes with a session check. |
| `frontend/src/types.ts` | Shared TypeScript shapes for knowledge bases, documents, media, RAG, citations, verification, and intelligence results. |
| `frontend/src/styles/index.css` | Global design tokens, layout, responsive rules, page/component styles, themes, loading, and error states. |
| `frontend/src/utils/language.ts` | Output-language labels/helpers shared by chat, media, and intelligence pages. |
| `frontend/index.html` | Vite HTML entry document. |
| `frontend/vite.config.ts` | Vite/React and Vitest configuration. |
| `frontend/playwright.config.ts` | Browser-test server, base URL, timeouts, and Chromium project. |
| `frontend/package.json` | React/Vite dependencies and build, typecheck, unit, and E2E commands. |

There is no `frontend/src/hooks/` or separate frontend service folder in the current repository. Page components use React hooks directly, and the API client is the shared service layer.

## Frontend pages

| File | Responsibility |
|---|---|
| `frontend/src/pages/LandingPage.tsx` | Public product explanation, workflow, limitations, privacy warning, and external/project links. |
| `frontend/src/pages/LoginPage.tsx` | Detects open/demo-password/accounts mode and performs demo login, account registration, and account login. |
| `frontend/src/pages/LegalPage.tsx` | Renders the public privacy, terms/demo, and security notices from static page definitions. |
| `frontend/src/pages/DashboardPage.tsx` | Aggregates KB/document/media/config data into overview metrics, recent sources, model details, and shortcuts. |
| `frontend/src/pages/KnowledgeBasesPage.tsx` | Creates and lists knowledge bases and opens the focused workspace route. |
| `frontend/src/pages/WorkspacePage.tsx` | Static knowledge-base-ID navigation hub; it does not load the collection record. |
| `frontend/src/pages/UploadPage.tsx` | Document/media file and URL intake, processing polling, source library, search/filter/sort, refresh, and retry. |
| `frontend/src/pages/DocumentPage.tsx` | Document status, original, extraction, preview, chunks, start/retry/delete, and bounded polling. |
| `frontend/src/pages/ChatPage.tsx` | Grounded chat, sessions, response/language/debug options, citations, verification, and evidence drawer. |
| `frontend/src/pages/VideoPage.tsx` | Media selection/player, transcript/search/seek, intelligence, media Q&A, exports, and bounded polling. |
| `frontend/src/pages/IntelligencePage.tsx` | Document summaries, comparisons, reports, citations, verification, and client-side Markdown export. |
| `frontend/src/pages/EvaluationPage.tsx` | Lists benchmark datasets/runs, executes a selected dataset, and exports run metrics. |
| `frontend/src/pages/FeedbackPage.tsx` | Displays aggregate feedback analytics; does not expose feedback submission/conversion. |
| `frontend/src/pages/TemplatesPage.tsx` | Lists/filter fixed action templates and forwards their prompt to chat. |
| `frontend/src/pages/SettingsPage.tsx` | Reads effective RAG/model/runtime settings and triggers model warmup. |

## Frontend components and API

| File | Responsibility |
|---|---|
| `frontend/src/api/client.ts` | Central same-origin `/api/v1` HTTP client, bearer/cookie auth, 30/210-second timeouts, errors, and typed endpoint wrappers. |
| `frontend/src/components/AppShell.tsx` | Desktop/mobile sidebar, topbar, command palette, theme, model status polling, settings, and logout. |
| `frontend/src/components/CitationList.tsx` | Renders source passages and links to document chunks or media timestamps. |
| `frontend/src/components/VerificationBadge.tsx` | Shows supported/partial/unsupported verification state. |
| `frontend/src/components/StatusBadge.tsx` | Converts document/media processing states into consistent visual labels. |
| `frontend/src/components/ProcessingTimeline.tsx` | Displays ordered document lifecycle stages. |
| `frontend/src/components/EmptyState.tsx` | Shared empty-state content and action. |
| `frontend/src/components/ErrorBoundary.tsx` | Catches uncaught React render errors and presents a recovery UI. |

## Backend entry and core configuration

| File | Responsibility |
|---|---|
| `backend/app/main.py` | Application factory; creates DB/storage/providers/queue, middleware, routes, lifespan tasks, and production SPA/static serving. |
| `backend/app/core/config.py` | Pydantic settings, aliases, bounds, cross-field validation, production auth requirements, and runtime-profile defaults. |
| `backend/app/core/security.py` | Password hashing, signed session/bearer claims, expiry, and authentication helpers. |
| `backend/app/core/middleware.py` | Access control, same-origin cookie protection, in-memory limits, body limits, concurrency, and request context. |
| `backend/app/core/errors.py` | Stable application/processing error envelopes and FastAPI exception handlers. |
| `backend/app/core/logging.py` | Structured JSON log configuration and sensitive-data-safe request context. |
| `backend/app/db/base.py` | SQLAlchemy declarative base plus timestamp and demo lifecycle mixins. |
| `backend/app/db/session.py` | Creates SQLAlchemy engines/session factories, including SQLite settings. |
| `backend/app/api/dependencies.py` | Request-scoped settings, database session, storage, model/provider, service, and engine dependencies. |
| `backend/app/api/router.py` | Includes the 11 route modules under the configured API prefix. |

## Backend route modules

| File | Responsibility |
|---|---|
| `backend/app/api/routes/health.py` | Liveness, dependency/schema readiness aliases, and protected safe operations status. |
| `backend/app/api/routes/auth.py` | Access config/session, shared demo login, account registration/login, logout, and current identity. |
| `backend/app/api/routes/knowledge_bases.py` | Knowledge-base create/list/detail. |
| `backend/app/api/routes/documents.py` | Document upload/list/detail/original/process/retry/status/extraction/preview/chunks/delete and background processing. |
| `backend/app/api/routes/rag.py` | KB ask/retrieve, effective RAG config, warmup, and chat-session CRUD. |
| `backend/app/api/routes/intelligence.py` | Bounded summary, comparison, and report generation. |
| `backend/app/api/routes/media.py` | Media upload/URL/list/detail/content/process/retry/transcript/search/intelligence/ask/export/delete. |
| `backend/app/api/routes/evaluation.py` | Evaluation dataset/case creation, benchmark execution, and run listing. |
| `backend/app/api/routes/feedback.py` | Feedback submission, aggregate analytics, and conversion to an evaluation case. |
| `backend/app/api/routes/templates.py` | Fixed action-template list and detail. |
| `backend/app/api/routes/demo.py` | Idempotent demonstration workspace/source/chat/evaluation seed endpoint. The frontend client exists but no current page calls it. |

## Backend services and repositories

| File | Responsibility |
|---|---|
| `backend/app/services/storage.py` | Safe local upload storage, streaming size enforcement, path resolution, deletion, and checksums. |
| `backend/app/services/documents.py` | Document create/list/get/delete business rules, duplicate/quota checks, and lifecycle fields. |
| `backend/app/services/processing.py` | Orchestrates extraction, chunking, embedding, relational index writes, optional LangChain FAISS, statuses, and failure cleanup. |
| `backend/app/services/retrieval.py` | Query embedding and candidate retrieval from the configured vector store. |
| `backend/app/services/reranking.py` | Dense/lexical/rerank scoring, query coverage, duplicate suppression, and source diversity. |
| `backend/app/services/query_rewriting.py` | Rewrites follow-up questions using bounded conversation history. |
| `backend/app/services/rag.py` | Full grounded QA flow and conversation persistence. |
| `backend/app/services/answer_processing.py` | Parses supported answer markers, direct/supporting text, citations, and safe not-found behavior. |
| `backend/app/services/verification.py` | Deterministic/LLM/skip claim-support verification. |
| `backend/app/services/language.py` | Detects Arabic/English and resolves requested output/transcription language. |
| `backend/app/services/intelligence.py` | Builds analysis context and generates summaries, comparisons, and multi-section reports. |
| `backend/app/services/media.py` | Cookie/Deno/yt-dlp safety plus media ingestion, download/subtitle/audio/transcription/index/intelligence orchestration. |
| `backend/app/services/evaluation.py` | Creates benchmark data and calculates stored case/run metrics by calling normal RAG. |
| `backend/app/services/feedback.py` | Stores ratings, aggregates analytics, and creates evaluation cases from feedback. |
| `backend/app/services/templates.py` | Holds and returns the fixed action-template library. |
| `backend/app/services/lifecycle.py` | Calculates expiry and updates access timestamps. |
| `backend/app/services/cleanup.py` | Safely removes expired unprotected inactive records, orphan files, and stale processing paths. |
| `backend/app/repositories/knowledge_bases.py` | Reusable KB create/get/list/count database operations. |
| `backend/app/repositories/documents.py` | Reusable document queries and persistence operations. |
| `backend/app/repositories/conversations.py` | Chat-session/message create/get/list/delete operations. |
| `backend/app/repositories/media.py` | Media/transcript/job/chapter/summary/attempt database operations. |

## Document and media processing modules

| File | Responsibility |
|---|---|
| `backend/app/document_processing/validation.py` | Supported document extension/media/signature/content checks and safe display filename. |
| `backend/app/document_processing/extraction.py` | PDF/TXT/DOCX extractors and extractor registry. |
| `backend/app/document_processing/ocr.py` | Converts a PDF page to an image and runs Tesseract OCR. |
| `backend/app/document_processing/tables.py` | Extracts PDF tables with pdfplumber and returns structured/table text metadata. |
| `backend/app/document_processing/chunking.py` | Custom deterministic text chunks with overlap, boundary handling, and location metadata. |
| `backend/app/media/validation.py` | Media extension/signature checks, YouTube detection, and public URL validation. |
| `backend/app/media/transcription.py` | Transcription interface, lazy faster-whisper provider, subtitle parser, and stable segment IDs. |
| `backend/app/media/intelligence.py` | Deterministic transcript summaries, chapters, actions, decisions, entities, lecture/study outputs, and glossary. |

## AI providers, engines, and utilities

| File | Responsibility |
|---|---|
| `backend/app/ai/interfaces.py` | Abstract embedding and generation provider contracts used for real and fake/test implementations. |
| `backend/app/ai/providers/huggingface.py` | Lazy sentence-transformer embeddings and Transformers generation with configured/fallback/extractive behavior. |
| `backend/app/ai/providers/lightweight.py` | Deterministic hashing embeddings and extractive generation for tests/fallback. |
| `backend/app/ai/vectorstores/base.py` | Vector-store interface and search-result shape. |
| `backend/app/ai/vectorstores/relational.py` | Default SQL-backed embedding store/search. |
| `backend/app/ai/prompting.py` | Custom-engine grounded-answer and query-rewrite prompt builders. |
| `backend/app/ai/hardware.py` | Resolves `auto` to CUDA, Apple MPS, or CPU. |
| `backend/app/ai/quantization.py` | Resolves none/4-bit/8-bit, using BitsAndBytes only on supported CUDA. |
| `backend/app/ai/generation_queue.py` | Bounds active/queued expensive calls and applies queue/execution timeouts. |
| `backend/app/ai/warmup.py` | Tracks and executes one model warmup lifecycle. |
| `backend/app/ai/model_io.py` | Explicit model/tokenizer save and local reload utility; not called by normal app startup. |
| `backend/app/ai/langchain_engine/runtime.py` | Lazily owns optional LangChain document pipeline, LLM, and chain suite. |
| `backend/app/ai/langchain_engine/document_pipeline.py` | Direct LangChain loaders/splitter/HuggingFaceEmbeddings/FAISS indexing, loading, deletion, and model identity checks. |
| `backend/app/ai/langchain_engine/llm.py` | Custom `EnterpriseGenerationLLM` plus direct Transformers pipeline and LangChain HuggingFacePipeline factories. |
| `backend/app/ai/langchain_engine/prompts.py` | LangChain `PromptTemplate` definitions for rewrite, QA, summary, comparison, verification, reports, and repair. |
| `backend/app/ai/langchain_engine/chains.py` | LCEL `prompt | llm | PydanticOutputParser` chains and bounded parser repair. |
| `backend/app/ai/langchain_engine/service.py` | Adapts LangChain retrieval/chain output to the same FastAPI RAG response contract. |
| `backend/app/ai/langchain_engine/schemas.py` | Pydantic structured output models used by LangChain parsers. |

## Database models and schemas

| File | Responsibility |
|---|---|
| `backend/app/models/knowledge_base.py` | KB parent and document/chat relationships. |
| `backend/app/models/document.py` | Document type/status, documents, extracted sections, chunks, and persisted embeddings. |
| `backend/app/models/conversation.py` | Chat session/message roles, content, citations, metadata, and verification. |
| `backend/app/models/media.py` | Media lifecycle plus transcript jobs/segments, summaries, chapters, attempts, and export records. |
| `backend/app/models/evaluation.py` | Benchmark datasets, cases, runs, results, and 25-case constant. |
| `backend/app/models/feedback.py` | User feedback and conversion link. |
| `backend/app/models/user.py` | Account email/password/role/active/timestamps. |
| `backend/app/schemas/knowledge_base.py` | KB create/read/list API shapes. |
| `backend/app/schemas/document.py` | Document, extraction, preview, section, chunk, and pagination shapes. |
| `backend/app/schemas/conversation.py` | Chat session/message create/read/list/detail shapes. |
| `backend/app/schemas/rag.py` | Ask/retrieve/answer/citation/verification/debug/config shapes. |
| `backend/app/schemas/intelligence.py` | Summary/comparison/report request and response shapes. |
| `backend/app/schemas/media.py` | Media URL/read/detail/transcript/search/intelligence shapes. |

Auth, evaluation, feedback, and template request models are defined close to their route modules rather than in dedicated schema files.

## Migrations

| File | Responsibility |
|---|---|
| `backend/migrations/env.py` | Connects Alembic to settings and SQLAlchemy metadata for online/offline migrations. |
| `backend/migrations/versions/0001_phase1_baseline.py` | Creates initial users, knowledge bases, and documents. |
| `backend/migrations/versions/0002_processing_rag_intelligence.py` | Adds processing columns/sections/chunks and chat session/message tables. |
| `backend/migrations/versions/0003_media_intelligence.py` | Adds media sources, transcript, summary, chapter, attempt, and export tables. |
| `backend/migrations/versions/0004_public_demo_lifecycle.py` | Adds lifecycle fields and creates evaluation/feedback tables for the public demo. |
| `backend/scripts/migrate_database.py` | Runs migrations to head during startup/deployment. |

## Automated tests

| Group | Files and responsibility |
|---|---|
| Backend API/core | `test_knowledge_bases.py`, `test_documents.py`, `test_processing.py`, `test_rag.py`, `test_intelligence.py`, `test_media.py`, `test_evaluation.py`, `test_health.py`, `test_multilingual.py` verify deterministic business/API behavior. |
| Backend policy/operations | `test_public_demo_auth.py`, `test_public_demo_limits_cleanup.py`, `test_policy_e2e.py`, `test_backup_restore.py` verify access, quotas, cleanup, security policy, and maintenance scripts. |
| Backend AI/runtime | `test_ai_providers.py`, `test_hardware.py`, `test_low_memory.py`, `test_langchain_course_layer.py` verify provider fallbacks, device/profile behavior, and direct course integration without remote models. |
| Opt-in backend models | `test_real_huggingface_rag.py`, `test_real_langchain_rag.py`, `test_real_transcription.py` are marker-gated and require model files/network or explicit opt-in. |
| Frontend unit | `frontend/src/api/client.test.ts`, component tests for citation/status, page tests for chat/document/login/settings, and `frontend/src/utils/language.test.ts`. |
| Browser | `frontend/e2e/enterprise-rag.spec.ts` exercises a deterministic browser/API fixture; `production-smoke.spec.ts` checks the built production app, navigation, routes, network failures, and console errors. |

`backend/tests/conftest.py` creates disposable settings, database/storage, fake embedding/generation/transcription providers, and a FastAPI client. It is test support, not counted as a test file.

## Docker, deployment, Nginx, backup, and configuration

| File | Responsibility |
|---|---|
| `Dockerfile` | Builds React, copies Deno, installs CPU Python/media/OCR dependencies, packages static assets, and selects the startup script. |
| `start-space.sh` | Creates runtime directories, migrates the database, and starts Uvicorn on port 7860. |
| `docker-compose.aws.yml` | AWS single-container service, environment, loopback port, persistent volumes, read-only cookie secret, limits, logs, and healthcheck. |
| `deploy/nginx/enterprise-rag.conf.template` | Example public reverse proxy, security headers, 55 MB body limit, asset caching, and API timeouts. |
| `deploy/systemd/enterprise-rag.service.template` | Starts/stops the AWS Compose app as a system service. |
| `deploy/systemd/enterprise-rag-cleanup.*` | Hourly cleanup one-shot service and timer. |
| `deploy/systemd/enterprise-rag-backup.*` | Daily backup one-shot service and timer. |
| `scripts/deploy-aws.sh` | Preflight, verified backup, image build/tag, replacement, health check, and image rollback. |
| `scripts/backup-production.sh` | Creates and verifies private local production backups. |
| `scripts/verify-backup.sh` | Validates archive scope, required files, manifest, and checksums without restoring. |
| `scripts/restore-production.sh` | Requires explicit confirmation, verifies/pre-backs-up/stops/restores/restarts/health-checks. |
| `.env.example` | Broad local configuration example with explanatory defaults. |
| `.env.low-memory.example` | Reduced model/context/concurrency profile. |
| `.env.aws-cpu.example` | Tracked AWS CPU/demo-password settings template; contains no deploy secret values. |
| `.env.huggingface.example` | Hugging Face Docker Space `/tmp` profile. |
| `.github/workflows/ci.yml` | Backend install/Ruff/deterministic tests and frontend install/type/build/unit checks. |

## Course compatibility and documentation

| Path | Responsibility |
|---|---|
| `course_demo/streamlit_app/` | Separate Streamlit direct/custom/LangChain demonstration. |
| `course_demo/ngrok/` | Explicit optional tunnel script and safety notes; never auto-started. |
| `course_demo/fine_tuning/` | Small PEFT/LoRA training, adapter save/reload, comparison, and notebook. |
| `course_demo/notebooks/` | Direct Hugging Face pipeline, model save/reload, quantization, LCEL/parser, LangChain RAG, and Streamlit/ngrok learning notebooks. |
| `README.md` | Main setup, product capabilities, validation, and links. |
| `docs/api.md` | Earlier API-oriented guide; use the current project-guide API inventory for all 60 operations. |
| `docs/architecture/` | Topic-specific architecture notes for auth, RAG engines, ingestion, evaluation, feedback, deployment, media, low memory, and multilingual behavior. |
| `docs/aws-cpu-deployment.md` | AWS CPU host preparation/deployment/operations instructions. |
| `docs/deployment.md`, `docs/huggingface-spaces.md` | General and Hugging Face deployment notes. |
| `docs/security.md`, `SECURITY.md` | Project security design and vulnerability reporting guidance. |
| `docs/testing.md` | Earlier test commands and strategy. |
| `docs/demo-video/`, `docs/case-study.md`, `docs/portfolio-case-study.md` | Demo, recording, portfolio, and presentation material; not implementation evidence by itself. |
| `scripts/generate_portfolio_screenshots.py` | Development asset helper that can generate portfolio screenshots/placeholders; it is not a runtime feature or proof that a page works. |
