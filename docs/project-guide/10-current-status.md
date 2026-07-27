# 10 — Current implementation status

Classifications describe the current repository, not a future roadmap.

## Fully implemented

| Feature | Evidence and boundary |
|---|---|
| Manual frontend routing and production SPA fallback | All exact/dynamic matches are in `frontend/src/App.tsx:110-164`; FastAPI serves assets and falls back to `index.html` for safe non-API paths at `backend/app/main.py:208-224`. This is implemented without React Router. |
| Same-origin API client, timeouts, and common auth errors | Production `/api/v1`, cookie/bearer behavior, 30/210-second abort handling, and 401 event are in `frontend/src/api/client.ts:27-147`; unit-tested in `client.test.ts`. |
| Knowledge-base create/list/detail API and create/list UI | `KnowledgeBasesPage.tsx`; `knowledge_bases.py:32-76`; model/repository/tests. Update/delete is not part of this classification. |
| Direct document upload, validation, storage, and deletion | `documents.py:103-119,319-334`; `DocumentService`, validation, storage, and `test_documents.py`. |
| PDF/TXT/DOCX extraction | `backend/app/document_processing/extraction.py:96-286`, OCR/table helpers, processing tests. OCR needs installed binaries as listed below. |
| Custom chunking | `TextChunker` in `chunking.py:26`; persisted chunk model and processing tests. |
| Custom relational vector index/search | `RelationalVectorStore` in `ai/vectorstores/relational.py:13`; embeddings stored in `DocumentChunk` at `models/document.py:155-158`. It is a custom direct implementation, not LangChain FAISS. |
| Hybrid scoring, reranking, duplicate suppression, and diversity | `RetrievalService` and `HybridReranker` (`services/retrieval.py:18`; `reranking.py:73`) with deterministic RAG tests. |
| Grounded chat and conversation persistence | Ask/chat-session routes in `api/routes/rag.py`; `RagService`; `ChatSession`/`ChatMessage`; Chat page and tests. No streaming/cancel is claimed. |
| Citations, source locations, and deterministic verification | RAG conversion/verification services and `CitationList`/`VerificationBadge`; RAG/intelligence/frontend tests. |
| Document summaries, comparisons, and reports | Three routes (`api/routes/intelligence.py:36-113`), three services (`services/intelligence.py:158,234,350`), page and backend tests. Results are returned, not persisted. |
| Direct MP3/MP4 and supported media ingestion | Media upload/list/detail/content/process/retry/delete routes, signature/duration validation, processing service, and deterministic media tests. Frontend delete is separate/partial. |
| Transcript storage, search, timestamp synchronization, and exports | Transcript/job/segment models; media transcript/search/export routes; Video page; media tests. |
| Transcript-backed media Q&A | Media ask route filters to the derived transcript document (`api/routes/media.py:425-463`); RAG returns timestamp citations. |
| Deterministic transcript intelligence | `TranscriptIntelligenceService` (`media/intelligence.py:57`) and media intelligence route/page. It is heuristic, not claimed as LLM output. |
| Evaluation execution and metrics backend | `EvaluationService.run_evaluation` (`services/evaluation.py:90-209`), four evaluation tables, routes, and tests. Dataset creation UI is partial. |
| Feedback submission/analytics/conversion backend | `FeedbackService` (`services/feedback.py:22-113`), routes and model. User-facing collection/conversion UI is partial. |
| Three access modes and signed sessions | Config validation, auth routes, middleware, user model, and `test_public_demo_auth.py`. Multi-tenant ownership is not claimed. |
| Demo lifecycle fields and path-safe cleanup service | `DemoLifecycleMixin`, `DemoCleanupService`, cleanup script/systemd timer, and cleanup tests. Actual host timer installation is configuration. |
| Liveness, readiness, and safe operations status | `api/routes/health.py:19-170` and health tests. Full observability stack is not claimed. |
| Fixed action-template library | 13 code-defined templates in `services/templates.py:21-192`, list/detail routes, and Templates page. Editable workflows are not claimed. |
| Production Docker build and static React/FastAPI packaging | `Dockerfile`, `start-space.sh`, static fallback, production Playwright spec. Actual current deployed image is not code-verifiable. |
| Backup verification and explicit restore scripts | `scripts/backup-production.sh`, `verify-backup.sh`, `restore-production.sh`, and `test_backup_restore.py`. Off-site backup is not included. |
| Health-gated image deploy and rollback script | `scripts/deploy-aws.sh:37-106` preflight/backup/build/replace/health/previous-image flow. Data rollback remains separate. |

## Implemented but needs configuration or external tools

| Feature | Required setup and evidence |
|---|---|
| Real Hugging Face embeddings | Provider is production code (`ai/providers/huggingface.py:16-154`) but first use needs accessible/cached model and resources. Real tests are `real_models` marker-gated. |
| Local generation model | Provider is wired at `main.py:150-158`; needs configured/cached model, disk/RAM, and model compatibility. It can fall back to another/extractive provider. |
| OCR and PDF table/image path | Code exists; Docker installs Poppler/Tesseract English/Arabic (`Dockerfile:23-32`). Host development must install them separately. |
| faster-whisper transcription | Provider is wired at `main.py:172-180`; needs `backend[media]`, ffmpeg, cached/downloadable model, CPU/RAM. Real transcription is marker-gated. |
| YouTube/remote media | yt-dlp, Deno, cookie copy, safe errors, URL validation, and tests exist (`services/media.py:170-266`; Dockerfile). Success needs permitted URL/network/current platform requirements and sometimes cookies/PO-token provider. |
| Optional LangChain RAG engine | Real direct loaders/splitter/HuggingFaceEmbeddings/FAISS/LCEL/PydanticOutputParser path exists under `ai/langchain_engine/`, selected by RAG engine setting, and requires processing into its index. |
| CUDA 4-bit/8-bit quantization | `BitsAndBytesConfig` creation exists in `ai/quantization.py:21-68`; needs supported Linux x86_64/CUDA and course dependency. AWS CPU does not use it. |
| Model warmup | Route/controller/UI exist, but completion needs model files/resources (`api/routes/rag.py:233-273`; Settings page). |
| Nginx/HTTPS | Nginx HTTP template and Certbot instructions exist. Actual hostname, certificate, renewal, and installed file are external. |
| AWS service/timers | systemd templates and AWS Compose exist; the current host installation/running state is **Not verified from the current codebase.** |
| Scheduled backups and cleanup | Units/scripts exist; operator must enable timers, provision paths, and monitor results. |

## Partially implemented

| Feature | What exists / what is missing |
|---|---|
| Knowledge-base workspace | Named routes are correct and Source/Chat/Intelligence preserve scope; the page still does not fetch, validate, or name the KB. |
| Knowledge-base lifecycle management UI | Create/list/open works; edit/delete/protect controls do not exist. |
| Evaluation dashboard | List/run/aggregate/export works; dataset/case creation and per-case result inspection are absent from UI. |
| Feedback experience | Analytics page works; no answer rating form, feedback record list, or conversion button. |
| Media lifecycle UI | Upload/list/retry/detail works; backend delete has no frontend action. |
| Demo onboarding | Seed route and frontend client exist; no visible seed button. |
| Chat regenerate/cancel | Regenerate only prefills a new prompt; stop icon does not abort. Normal ask/error/loading is implemented. |
| Templates as workflows | Cards/filter/prompt forwarding work; output schemas are metadata and there is no structured executor/editor. |
| Dashboard quality metrics | Counts/config/recent sources and source-readiness ratio are live; there is still no measured retrieval-quality or answer-quality score on this page. |
| Recent navigation | Recent labels are fixed shortcuts rather than data-backed history. The current-workspace label is now non-interactive status text. |
| Accounts identity | Registration/login/user table work; `/auth/me` is synthetic and content is not user-owned/scoped. |
| Observability | JSON logs, request IDs, health/readiness, queue/storage/operation status exist; no metrics/tracing/alerts/dashboard stack. |
| Document/media intelligence history | Chat/evaluation/media derived records persist; document summary/comparison/report results do not. |

## Experimental or course-only

| Feature | Evidence |
|---|---|
| Streamlit course application | `course_demo/streamlit_app/app.py` and README; installed in dev/course extras, excluded from production image. |
| Optional ngrok tunnel | `course_demo/ngrok/launch_tunnel.py`; explicit manual command only, never auto-started. |
| PEFT/LoRA fine-tuning | `course_demo/fine_tuning/train_lora.py` uses synthetic small data, saves/reloads adapter, and compares output. Not wired to FastAPI. |
| Course notebooks | `course_demo/notebooks/` directly demonstrates pipeline, save/reload, quantization, LCEL/parser, LangChain RAG, and Streamlit/ngrok. Notebook execution state/current remote models are not product evidence. |
| Model bundle save/reload helper | `backend/app/ai/model_io.py:8-55` is real/tested utility code but not called by normal product startup. |
| Portfolio screenshot generator | `scripts/generate_portfolio_screenshots.py` is an asset helper and can create placeholders; it is not runtime validation. |

## Placeholder or presentation-only

| Item | Evidence |
|---|---|
| Sidebar recent labels | Fixed “Remote policy research” and “Transcript insights” links at `AppShell.tsx:180-190`. |
| User avatar/profile | Fixed `ER`/“Demo session” display (`AppShell.tsx:271`); no profile menu. |

## Broken or likely broken

No confirmed broken build/test/runtime feature remains from this review. The verified workspace route and Intelligence scope defects were fixed with unit coverage. Environment-dependent model/YouTube failures are configured limitations, not automatically code defects.

## Not found in the codebase

For each item below: **Not verified from the current codebase.**

- React Router or another frontend routing library.
- Knowledge-base edit/delete route or UI.
- Full admin dashboard, user administration, role assignment, or admin-only route policy.
- Multi-tenant row ownership/authorization.
- Speaker diarization.
- Malware scanning/quarantine.
- PostgreSQL, pgvector, Chroma production integration, S3/object storage, Redis/Celery, or a distributed durable job queue.
- Streaming chat tokens or server-side request cancellation.
- Prometheus, OpenTelemetry, external tracing, alert manager, or an in-product observability dashboard.
- Off-site/encrypted backup provider or key-management integration.
- DuckDNS updater, hostname, token, or live DNS state.
- Checked-in TLS certificate/private key or proof of a current Certbot renewal.
- Kubernetes, Terraform, CloudFormation, or autoscaling configuration.
- Automated fine-tuning from user uploads.
- Formal accessibility audit, penetration-test report, load-test report, or compliance certification.

## Direct library/tool distinctions

- Default embeddings/vector search/RAG are custom production implementations using sentence-transformers, SQLAlchemy/SQLite embedding bytes, and custom retrieval/reranking/services.
- The alternate LangChain engine directly uses course libraries; it is not merely a custom equivalent (`backend/app/ai/langchain_engine/`).
- `StructuredOutputParser` is not found; direct structured LCEL uses `PydanticOutputParser` (`chains.py:8,55-106`).
- Chroma integration is not found. FAISS is the implemented LangChain vector store.
- Streamlit/ngrok/LoRA are course demonstrations, not the React/FastAPI deployment.
