# 02 — Feature-by-feature guide

This chapter follows real requests from the browser to the API, service, database, and tests. “Automatic test” means a deterministic test unless the entry explicitly says real model/network.

## Knowledge bases

- **What and why:** A knowledge base is the parent collection for documents, media, chat sessions, evaluation datasets, and feedback. It keeps retrieval scoped to a chosen collection.
- **User flow:** `KnowledgeBasesPage` calls `createKnowledgeBase` or `listKnowledgeBases` (`frontend/src/pages/KnowledgeBasesPage.tsx:7-48`; `frontend/src/api/client.ts:149-162`). FastAPI handles this in `backend/app/api/routes/knowledge_bases.py:32-76`, using `KnowledgeBaseRepository`.
- **Main code:** `KnowledgeBase` in `backend/app/models/knowledge_base.py:14-30`; repository in `backend/app/repositories/knowledge_bases.py`; lifecycle helper in `backend/app/services/lifecycle.py`.
- **API and data:** `GET/POST /api/v1/knowledge-bases`, `GET /api/v1/knowledge-bases/{id}`; table `knowledge_bases`.
- **Configuration:** `ENTERPRISE_RAG_MAX_KNOWLEDGE_BASES`, `ENTERPRISE_RAG_DEMO_DATA_RETENTION_HOURS`.
- **Manual test:** Create a collection, refresh, open it, then reach the configured quota and verify a 422-style actionable error.
- **Automatic tests:** `backend/tests/test_knowledge_bases.py`; lifecycle/quota behavior in `test_public_demo_limits_cleanup.py`.
- **Limitations:** No update or delete endpoint/UI. The workspace detail page does not fetch the record. There is no account/tenant owner field.

## Document upload and validation

- **What and why:** Saves an original PDF, TXT, or DOCX only after checking filename, declared type, file signature/content, size, duplicate checksum, collection quota, and safe path.
- **User flow:** `UploadPage` -> `uploadDocument` -> `POST /knowledge-bases/{id}/documents` (`frontend/src/pages/UploadPage.tsx:190-220`; `backend/app/api/routes/documents.py:103-119`). `DocumentService` and `LocalFileStorage` create the record and stored file.
- **Main code:** `backend/app/services/documents.py:DocumentService`; `backend/app/document_processing/validation.py:33-84`; `backend/app/services/storage.py:20`; upload limiter middleware in `backend/app/core/middleware.py`.
- **API and data:** Upload/list/detail/delete endpoints; `documents` table and file below `storage_path`.
- **Configuration:** upload byte/MB limits, request-body limit, files-per-KB, concurrent uploads, upload rate, retention.
- **Manual test:** Upload each valid type, a renamed binary, a duplicate, an oversize body, and an unsafe filename. Confirm errors do not leave unintended records/files.
- **Automatic tests:** `backend/tests/test_documents.py`, `test_processing.py`, `test_policy_e2e.py`.
- **Limitations:** Frontend extension checks are convenience only. The configured Nginx and app limits must agree. There is no virus scanner or content moderation service in the repository.

## PDF, TXT, and DOCX extraction

- **What and why:** Turns supported files into text sections that later processing can chunk and cite.
- **Flow:** `DocumentProcessingService` selects an extractor, stores `DocumentSection` rows and extraction metadata, then advances status (`backend/app/services/processing.py:26`). `PdfExtractor` uses pypdf, OCR fallback for low-text pages, and table extraction (`backend/app/document_processing/extraction.py:96-176`). TXT uses strict text handling (`:177-208`); DOCX reads paragraphs/tables (`:209-270`).
- **Main code:** `extraction.py`, `ocr.py:OcrEngine`, `tables.py:TableExtractor`, `validation.py`.
- **API and data:** `POST /documents/{id}/process`; `GET /extraction` and `/preview`; `documents`, `document_sections`.
- **Configuration:** `ENTERPRISE_RAG_MAX_DOCUMENT_PAGES`; Docker supplies Poppler and Tesseract English/Arabic (`Dockerfile:23-32`).
- **Manual test:** Use a text PDF, scanned English/Arabic PDF, table PDF, TXT, DOCX, corrupt file, and over-page-limit file. Inspect warnings and preview.
- **Automatic tests:** `backend/tests/test_processing.py`; document API behavior in `test_documents.py`.
- **Limitations:** OCR quality depends on scan quality and installed languages. Complex layout/table reconstruction can lose formatting. Password-protected or malformed documents may fail.

## Chunking

- **What and why:** Splits long extracted text into overlapping, citation-friendly pieces with page/section/character metadata.
- **Flow:** The default path calls custom `TextChunker` (`backend/app/document_processing/chunking.py:26`); the optional LangChain path uses `RecursiveCharacterTextSplitter` (`backend/app/ai/langchain_engine/document_pipeline.py:54-62`).
- **API and data:** Processing writes `document_chunks`; `GET /documents/{id}/chunks` pages through them.
- **Configuration:** `ENTERPRISE_RAG_CHUNK_SIZE`, `ENTERPRISE_RAG_CHUNK_OVERLAP`; overlap must be smaller than size (`backend/app/core/config.py:190-197`).
- **Manual test:** Process a document longer than one chunk; inspect chunk boundaries, overlap, page metadata, stable order, and counts.
- **Automatic tests:** `backend/tests/test_processing.py`; LangChain pipeline tests in `test_langchain_course_layer.py`.
- **Limitations:** Token count is an estimate in the custom model. Chunk boundaries are heuristic and can split a logical argument.

## Embeddings and vector storage

- **What and why:** Converts queries and source chunks into normalized vectors so semantically similar text can be found.
- **Flow:** `HuggingFaceEmbeddingProvider` lazily loads sentence-transformers, applies E5 query/passage prefixes when appropriate, batches work, and caches recent query vectors (`backend/app/ai/providers/huggingface.py:16-154`). The default `RelationalVectorStore` stores float32 bytes in `document_chunks.embedding` (`backend/app/ai/vectorstores/relational.py:13`; `backend/app/models/document.py:155-158`). The optional LangChain path uses `HuggingFaceEmbeddings` and persistent FAISS (`backend/app/ai/langchain_engine/document_pipeline.py:36-255`).
- **API and data:** Document/media processing writes embeddings; `/retrieve`, `/ask`, and intelligence read them.
- **Configuration:** embedding model, batch size, device, cache path, local-files-only, query-cache size, RAG engine, LangChain index path.
- **Manual test:** Process a source, confirm indexed count equals chunk count, query a paraphrase, restart, and confirm retrieval still works. If changing the embedding model, reprocess and verify no mismatch.
- **Automatic tests:** deterministic provider/vector behavior in `test_ai_providers.py`, `test_rag.py`, `test_processing.py`; opted-in `test_real_huggingface_rag.py` and `test_real_langchain_rag.py`.
- **Limitations:** First use may download a model. SQLite scans are suitable for a small demo, not a large vector corpus. LangChain indexes are separate files and must match the selected embedding model.

## Hybrid retrieval, reranking, and source diversity

- **What and why:** Combines vector similarity with word overlap, then reranks, removes near-duplicates, and limits too many passages from one document.
- **Flow:** `RetrievalService` embeds the query and obtains candidates (`backend/app/services/retrieval.py:18`). `HybridReranker` computes dense, lexical, rerank, and query-coverage values (`backend/app/services/reranking.py:73`). The result becomes `RetrievedSourceRead` and citations.
- **API and data:** Debug directly with `POST /knowledge-bases/{id}/retrieve`; RAG uses the same services. Reads indexed `document_chunks` joined to documents.
- **Configuration:** top-k, candidate pool, similarity threshold, dense/lexical/rerank weights, near-duplicate threshold, minimum query coverage, maximum sources per document.
- **Manual test:** Add two overlapping sources, query an exact term and a paraphrase, inspect debug scores, and confirm duplicate passages do not dominate.
- **Automatic tests:** `backend/tests/test_rag.py`, `test_policy_e2e.py`, `test_multilingual.py`.
- **Limitations:** Lexical tokenization/rules are lightweight. Scores are not calibrated probabilities. There is no learned cross-encoder reranker.

## Grounded chat, query rewrite, and conversation history

- **What and why:** Answers a question using retrieved source text and persists a reusable conversation.
- **Flow:** `ChatPage` calls `askKnowledgeBase` (`frontend/src/pages/ChatPage.tsx:175-220`). The route creates the selected RAG service (`backend/app/api/routes/rag.py:50-115`). `RagService` rewrites with recent history, retrieves, checks support, builds a grounded prompt, generates, post-processes, verifies, and saves user/assistant messages (`backend/app/services/rag.py:97`).
- **Main code:** `query_rewriting.py:QueryRewriteService`, `ai/prompting.py`, `answer_processing.py:AnswerPostProcessor`, conversation repository/model.
- **API and data:** `/knowledge-bases/{id}/ask` and chat-session endpoints; `chat_sessions`, `chat_messages`, `document_chunks`.
- **Configuration:** engine, model, generation parameters, context/history limits, retrieval thresholds, generation/retrieval/queue timeouts, rate limits.
- **Manual test:** Ask a follow-up that relies on history, reopen the session, ask unsupported content, delete the session, and inspect debug output.
- **Automatic tests:** `test_rag.py`, `test_multilingual.py`, `test_policy_e2e.py`, `ChatPage.test.tsx`; opted-in real model tests.
- **Limitations:** No streaming response. No working cancel button. In-memory queue/rate limits are per process. Model quality depends on the configured local model.

## Citations and verification

- **What and why:** Connects answer claims back to passages and labels support so users can inspect evidence.
- **Flow:** Retrieved results become citations in `backend/app/services/rag.py:37-95`. `VerificationService` applies deterministic evidence checks by default (`backend/app/services/verification.py:50`). The frontend renders locations, support scores, passages, and badges (`frontend/src/components/CitationList.tsx`; `VerificationBadge.tsx`).
- **API and data:** Included in RAG/intelligence response models and saved in `chat_messages.citations`/`verification`.
- **Configuration:** `ENTERPRISE_RAG_VERIFICATION_MODE` (`deterministic`, `llm`, or `skip`) and retrieval/support thresholds.
- **Manual test:** Confirm every supported claim has a resolvable document/chunk or media timestamp; follow document links and test an unsupported question.
- **Automatic tests:** `test_rag.py`, `test_intelligence.py`, `CitationList.test.tsx`, `ChatPage.test.tsx`.
- **Limitations:** Deterministic verification is a heuristic, not factual proof. LLM verification adds model dependence. A citation supports only the shown passage, not necessarily every sentence nearby.

## Summaries, comparisons, and reports

- **What and why:** Produces source-grounded higher-level analysis without requiring a free-form chat prompt.
- **Flow:** `IntelligencePage` sends structured requests (`frontend/src/api/client.ts:265-330`). `AnalysisContextBuilder` selects ready source text; `SummaryService`, `ComparisonService`, and `ReportService` generate/verify structured output (`backend/app/services/intelligence.py:40-443`). Report generation is bounded per section and can return a marked partial result.
- **API and data:** `POST /intelligence/summaries`, `/comparisons`, `/reports`; reads document tables, returns results without a document-intelligence persistence table.
- **Configuration:** context maximum, summary/comparison/report timeouts, report-section timeout, intelligence max tokens, language/model settings.
- **Manual test:** Generate all three modes from two sources in English and Arabic; inspect citations, partial flag, and Markdown export.
- **Automatic tests:** `test_intelligence.py`, `test_multilingual.py`, `test_low_memory.py`.
- **Limitations:** Results are not saved server-side. Comparison is one consolidated generation; report uses several calls and may be partial. UI does not honor workspace `knowledgeBase` query.

## Direct media upload and public URL ingestion

- **What and why:** Adds audio/video as a searchable knowledge source. Direct upload is the reliable path; public URLs are convenience imports.
- **Flow:** Direct files go to `POST /knowledge-bases/{id}/media`; public URLs to `/media/from-url` (`backend/app/api/routes/media.py:137-189`). `MediaIngestionService` validates file signatures or public URLs, calculates checksums, stores records, and queues processing (`backend/app/services/media.py:268`). URL validation rejects unsafe schemes/addresses and validates redirects (`backend/app/media/validation.py:82-109` and media service downloader code).
- **API and data:** media upload/list/detail/content/process/retry/delete; `media_sources` plus storage files.
- **Configuration:** media upload and duration limits, download/processing timeouts, concurrency, URL-import/transcription rate limits, retention.
- **Manual test:** Direct MP3/MP4 and an allowed public URL; loopback/private/link-local/redirect-to-private URLs; duplicate and duration limits.
- **Automatic tests:** `test_media.py`, `test_policy_e2e.py`, `test_public_demo_limits_cleanup.py`.
- **Limitations:** Remote host behavior can change. Only HTTP(S) public URLs are intended. Frontend does not expose media deletion.

## YouTube handling

- **What and why:** Uses yt-dlp to read metadata/subtitles or obtain an audio-capable stream for transcription.
- **Flow:** `MediaProcessingService` invokes yt-dlp with an audio-safe `bestaudio/best` strategy. `prepare_runtime_ytdlp_cookie` copies a configured read-only secret to a private writable `/tmp/enterprise-rag` file, applies mode 0600, refreshes it by source modification time, and uses a process lock (`backend/app/services/media.py:170-266`). Deno availability and known failure strings are converted to safe terminal messages. Docker installs Deno (`Dockerfile:13-21`).
- **API and data:** Same public-URL media endpoints; safe error code/message stored in `media_sources`, technical details are not sent in the normal response schema.
- **Configuration:** `ENTERPRISE_RAG_YTDLP_COOKIES_FILE`; deployment mounts `/home/ubuntu/youtube-cookies.txt:/run/secrets/youtube-cookies.txt:ro` (`docker-compose.aws.yml:21`). `DENO_DIR` controls its cache.
- **Manual test:** In the final container confirm `deno --version`; use a permitted test URL with `yt-dlp --cookies /tmp/enterprise-rag/youtube-cookies.txt --skip-download`; test expired cookies and a URL with no audio format.
- **Automatic tests:** deterministic cookie/permissions/log redaction/Deno/error classification tests in `backend/tests/test_media.py`.
- **Limitations:** YouTube can require new challenge support, PO Tokens, authenticated/age/region access, or reject cloud IPs. Cookies expire. The repository cannot guarantee every URL. Never log or expose cookies.

## Transcription and transcript-backed retrieval

- **What and why:** Converts speech into timestamped text, then indexes that text so media can be searched and cited.
- **Flow:** Processing tries subtitles first. If unavailable, ffmpeg extracts audio and `FasterWhisperTranscriptionProvider` runs CPU int8 transcription (`backend/app/media/transcription.py:46-183`). Segments are stored; a transcript document/chunks are created; media Q&A filters to that document (`backend/app/api/routes/media.py:425-463`).
- **API and data:** transcript/read/search/intelligence/ask endpoints; `transcript_jobs`, `transcript_segments`, `documents`, `document_chunks`.
- **Configuration:** model `tiny|base|small`, CPU/int8, language, threads, workers, beam size, unload-after-use, duration and processing limits.
- **Manual test:** Transcribe short English and Arabic media, inspect timestamps/language, search, and ask a question that cites a timestamp.
- **Automatic tests:** deterministic fake-provider media tests in `test_media.py`; real download/model run in marked `test_real_transcription.py` with `RUN_REAL_TRANSCRIPTION_TESTS=1`.
- **Limitations:** CPU transcription can be slow and memory-heavy. Speaker diarization is not implemented. Accuracy depends on audio and language. Real tests require model files.

## Media intelligence and exports

- **What and why:** Turns a transcript into browsable summaries, chapters, decisions, actions, entities, notes, quiz questions, glossary, and export files.
- **Flow:** `TranscriptIntelligenceService` uses deterministic transcript heuristics (`backend/app/media/intelligence.py:57`) during media processing. The route assembles stored summary/chapter/segment data (`backend/app/api/routes/media.py:382-423`). Export requests render TXT, Markdown, or JSON and record the event (`:465-521`).
- **API and data:** `/media/{id}/intelligence`; `/export/{export_kind}`; `media_summaries`, `media_chapters`, `media_export_records`.
- **Configuration:** output language and media limits; model name stored for provenance even though this service is deterministic.
- **Manual test:** Process meeting and lecture samples; inspect each section and validate transcript.txt, transcript.md, transcript.json, and summary.md content/type.
- **Automatic tests:** `backend/tests/test_media.py`.
- **Limitations:** The intelligence is heuristic, not a full LLM analysis. Owners/deadlines/speakers may be missing or approximate. Export history stores kind/format, not the exported bytes.

## Evaluation benchmarks

- **What and why:** Runs a fixed question set against the normal RAG engine to compare repeatable metrics.
- **Flow:** API creates datasets/cases; `EvaluationService.run_evaluation` calls `RagService.ask` for every case and stores result/run metrics (`backend/app/services/evaluation.py:34-209`). The page lists/runs/exports existing datasets.
- **API and data:** dataset/case/run endpoints; four `evaluation_*` tables.
- **Configuration:** normal RAG/model/timeouts; maximum 25 cases per dataset is code constant (`backend/app/models/evaluation.py:11`).
- **Manual test:** Create supported/unsupported cases, run, compare per-run totals and response latency.
- **Automatic tests:** `backend/tests/test_evaluation.py`.
- **Limitations:** No frontend dataset/case editor or per-case result view. Token coverage is a simple correctness proxy. Evaluation calls can be expensive/slow.

## Feedback analytics and conversion

- **What and why:** Stores helpful/unhelpful judgments and can turn a feedback record into an evaluation case.
- **Flow:** The API calls `FeedbackService.submit_feedback`, `get_analytics`, or `convert_to_evaluation_case` (`backend/app/services/feedback.py:22-113`). The frontend API has all three clients, but `FeedbackPage` only loads analytics/datasets and presents no record-level actions.
- **API and data:** feedback submit/analytics/convert endpoints; `user_feedback`, `evaluation_datasets`, `evaluation_cases`.
- **Configuration:** no dedicated variable; normal auth/lifecycle/database settings apply.
- **Manual test:** Use curl to submit helpful/unhelpful records, view analytics, convert one into a dataset, and confirm the case count changes.
- **Automatic tests:** empty analytics and related evaluation behavior in `backend/tests/test_evaluation.py`.
- **Limitations:** User-facing submission/conversion is missing. `chat_message_id` is a string without a database foreign key. Conversion uses English and the comment/answer as expected text.

## Authentication and access modes

- **What and why:** Supports open local access, one shared password for a public demo, or user accounts.
- **Flow:** `AccessControlMiddleware` validates public routes, bearer tokens, or signed HttpOnly cookies. Auth routes issue/clear sessions; account passwords are bcrypt hashes (`backend/app/api/routes/auth.py:67-248`; `backend/app/core/security.py`; `backend/app/core/middleware.py`). Cookie-authenticated unsafe requests also receive same-origin checks.
- **API and data:** auth config/session/demo-login/register/login/logout/me; `users` only for accounts mode.
- **Configuration:** access mode, demo hash, session secret/expiry/cookie name/secure, login attempts/lockout, CORS.
- **Manual test:** Exercise all three modes, expired/tampered token, cross-origin unsafe request, lockout, inactive account, and logout.
- **Automatic tests:** `backend/tests/test_public_demo_auth.py`; `frontend/src/pages/LoginPage.test.tsx`; Playwright demo-login path.
- **Limitations:** Account mode does not attach user IDs to knowledge/data rows, so it is not multi-tenant authorization. `/auth/me` builds a fixed demo-style identity from claims rather than loading an account record (`backend/app/api/routes/auth.py:241-248`). Login/rate state is in process memory.

## Demo mode, expiry, protected records, and cleanup

- **What and why:** Gives public-demo data an expiry time while exempting protected records and avoiding active jobs.
- **Flow:** `DemoLifecycleMixin` adds access/expiry/protection (`backend/app/db/base.py:24-31`). Create/upload services assign expiry. `DemoCleanupService` selects expired unprotected inactive KB/document/media records, deletes database rows/files, removes old orphans/temp paths, and writes a protected operation marker (`backend/app/services/cleanup.py:59-273`). systemd runs it hourly.
- **API and data:** no public delete-expired API; `/operations/status` reads safe markers. Lifecycle fields occur on KB/doc/media tables.
- **Configuration:** demo retention hours, temporary-file retention hours, storage path.
- **Manual test:** Use the cleanup script dry-run, create expired/protected/active records in a test database, then run cleanup and verify only eligible data is removed.
- **Automatic tests:** `backend/tests/test_public_demo_limits_cleanup.py`.
- **Limitations:** Scheduling exists only when the systemd timer is installed/enabled. Backup retention is separate, so deleted demo content can remain inside a backup until backup expiry.

## Health, readiness, and lightweight observability

- **What and why:** Separates process liveness from dependency/schema readiness and exposes safe runtime/maintenance status.
- **Flow:** `/health` returns a simple live response. `/readiness` and `/ready` check database access, current Alembic revision, and writable storage/cache directories (`backend/app/api/routes/health.py:19-112`). `/operations/status` reports uptime/build/profile/model/queue/storage and last safe cleanup/backup marker without secrets (`:116-170`). JSON logging and request IDs are configured in `backend/app/core/logging.py` and middleware.
- **Configuration:** environment, git commit, paths, runtime/model settings; Docker healthcheck uses `/health` (`docker-compose.aws.yml:23-28`).
- **Manual test:** Call all endpoints; make a required path unwritable or schema stale only in a disposable environment and confirm readiness fails while liveness stays up.
- **Automatic tests:** `backend/tests/test_health.py`, `test_policy_e2e.py`.
- **Limitations:** No Prometheus, OpenTelemetry, tracing backend, alerting, or UI observability dashboard. `/health` alone does not prove models/database are ready.

## Local model runtime, quantization, cache, and warmup

- **What and why:** Keeps embeddings and generation local, supports bounded queues/timeouts, and avoids duplicate model loads on small hosts.
- **Flow:** `create_app` wires device, providers, optional LangChain wrapper, warmup controller, transcription provider, and `GenerationQueue` (`backend/app/main.py:114-188`). `HuggingFaceGenerationProvider` tries the configured model, a fallback, then an extractive local fallback. `resolve_quantization` creates `BitsAndBytesConfig` only where supported (`backend/app/ai/quantization.py:21-68`).
- **API and data:** `/rag/config`, `/rag/warmup`; cache directory, no model-state table.
- **Configuration:** model IDs/device/local-only/cache; 4bit/8bit/none; generation parameters; runtime profile; warm/unload/thread/cache/queue/timeouts.
- **Manual test:** Inspect cold config, warm models, ask, inspect ready config, restart with cache, and test a deliberately unavailable model in a disposable profile.
- **Automatic tests:** `test_ai_providers.py`, `test_hardware.py`, `test_low_memory.py`; opted-in real-model tests.
- **Limitations:** First download requires network unless pre-cached. BitsAndBytes quantization is not used on the AWS CPU profile. A 4 GB host has strict quality/context/concurrency tradeoffs. Model bundle save/reload helpers exist but are not the normal app path.

## LangChain compatibility engine

- **What and why:** Provides direct course-library coverage while preserving the product API. It is a real alternate engine, not a custom equivalent.
- **Flow:** `LangChainEngineRuntime` lazily creates a `LangChainDocumentPipeline` and LLM. Loaders -> `RecursiveCharacterTextSplitter` -> `HuggingFaceEmbeddings` -> FAISS persist per knowledge base. `CourseChainSuite` builds `PromptTemplate | llm | PydanticOutputParser` chains with bounded repair (`backend/app/ai/langchain_engine/document_pipeline.py:36-255`; `chains.py:55-106`). `EnterpriseGenerationLLM` wraps the existing product provider in low-memory mode (`llm.py:14-90`).
- **API and data:** Same processing/ask/intelligence endpoints; index files below `langchain_index_path`, relational metadata remains in SQLite.
- **Configuration:** RAG engine, LangChain index path, force wrapper, parser retries, embedding/model/device/generation values.
- **Manual test:** Select LangChain, process a fresh source, confirm FAISS files, ask through normal chat, delete/reindex, and test a parser-repair case.
- **Automatic tests:** `backend/tests/test_langchain_course_layer.py`; `test_real_langchain_rag.py` when opted in.
- **Limitations:** Requires separate FAISS index persistence and reindex after engine/embedding changes. It can load extra model objects unless force-wrapper is used. `StructuredOutputParser` is not used; PydanticOutputParser is the implemented parser.

## Templates

- **What and why:** Supplies curated prompt starters for analysis, contracts, study, meetings, and HR.
- **Flow:** `TemplateService` returns fixed `TEMPLATES`; page filtering is client-side and Run Workflow forwards the prompt to chat (`backend/app/services/templates.py:21-203`; `frontend/src/pages/TemplatesPage.tsx:31-101`).
- **API and data:** template list/detail endpoints; no table.
- **Configuration:** none.
- **Manual test:** List and fetch every template, filter categories, and open a prompt in chat.
- **Automatic tests:** route availability through policy/browser coverage; no dedicated template service test file.
- **Limitations:** No create/edit/persistence. Declared `output_schema_type` is metadata; normal chat does not enforce it.

## Backup, restore, deploy, and rollback

- **What and why:** Protects persistent demo data before release/restore and returns to a previous image when health checks fail.
- **Flow:** `backup-production.sh` requests a SQLite-safe backup inside the container, collects data/uploads, creates a secret-free environment template, manifest, and checksums, applies private permissions, verifies the archive, and applies retention. `restore-production.sh` verifies target/scope, makes a pre-restore backup, stops app, restores, restarts, and health-checks. `deploy-aws.sh` preflights environment/cookies, backs up, builds a commit-tagged image, replaces the app, and rolls back image on failed health.
- **Data/config:** named data volume, bind-mounted backup directory; operational variables in the environment guide.
- **Manual test:** Use a disposable deployment: create data, backup/verify, change data, restore with `--confirm`, confirm original data and health. Test deployment `--dry-run` before a real release.
- **Automatic tests:** `backend/tests/test_backup_restore.py`; shell syntax/behavior exercised there.
- **Limitations:** Backups are local host files unless an operator copies them elsewhere. No off-site encryption/key management is implemented. A backup can contain uploaded content. Restore causes downtime.

## Rate limits, queues, and request safety

- **What and why:** Protects a small demo from oversized bodies and too many heavy operations.
- **Flow:** middleware enforces authentication, rate classes, upload concurrency, declared body size, CORS, and request IDs (`backend/app/main.py:190-201`; `backend/app/core/middleware.py`). Storage streaming enforces actual upload bytes. `GenerationQueue` bounds heavy work (`backend/app/ai/generation_queue.py:35`).
- **Configuration:** request/upload/media sizes; per-minute upload/generation/transcription/URL rates; concurrent upload/heavy/generation values; queue size/timeouts; CORS.
- **Manual test:** Use a disposable instance to send over-limit bodies, bursts, and concurrent heavy calls; confirm 4xx/429/503 responses, recovery after window, and no endless UI loading.
- **Automatic tests:** `test_public_demo_limits_cleanup.py`, `test_policy_e2e.py`, `test_low_memory.py`.
- **Limitations:** Limiters/queues are in memory and not shared across multiple workers/containers. Content-Length checks alone are not relied on, but Nginx/app/storage values still need coordination.

## Admin and maintenance features

There is no admin page, role-management UI, user list, knowledge-base moderation UI, or protected-record editing API. Maintenance is command-line/systemd based: migrations, cleanup, backups, restore, deployment, and safe operations status. The `admin` enum value exists (`backend/app/models/user.py:13-15`), but route-level admin-only enforcement is **Not verified from the current codebase.**

## Course-only demonstrations

The separate course area directly demonstrates Streamlit (`course_demo/streamlit_app/app.py`), optional explicit ngrok (`course_demo/ngrok/launch_tunnel.py`), Hugging Face `pipeline()`, model save/reload notebooks, 4/8-bit BitsAndBytes, LCEL and output parsing, and PEFT/LoRA (`course_demo/fine_tuning/train_lora.py`). These are useful learning artifacts, but they are not started by the production Docker entry point and do not change the product model from user data. Their downloads and compute requirements must be tested separately.
