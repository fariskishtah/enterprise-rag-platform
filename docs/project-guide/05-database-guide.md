# 05 — Database guide

## Database type and location

EnterpriseRAG uses SQLAlchemy. The default URL is SQLite: `sqlite:///./data/enterprise_rag.db` (`backend/app/core/config.py:46`). Because that is relative, the file depends on the process working directory; normal backend development runs from `backend/`, so it is usually `backend/data/enterprise_rag.db`.

Deployment profiles override it:

- The Dockerfile's Hugging Face default is `sqlite:////tmp/enterprise_rag.db` (`Dockerfile:64`). This is ephemeral unless the platform adds persistence.
- The AWS example uses the persistent `/data` volume. Its effective URL is `sqlite:////data/enterprise_rag.db`, provided through `.env.aws-cpu.example` and `docker-compose.aws.yml:18-22`.
- Tests create disposable databases through `backend/tests/conftest.py`; they must not point at production data.

SQLite is a single-file relational database. It is simple to back up and suitable for this one-container demo. It is not the same as a network database designed for many application replicas.

## Relationship map

```text
knowledge_bases
  ├─ documents
  │    ├─ document_sections
  │    └─ document_chunks ────────┐
  ├─ chat_sessions               │ also points to knowledge_bases
  │    └─ chat_messages          │
  ├─ media_sources ──────────────┘
  │    ├─ transcript_jobs
  │    ├─ transcript_segments
  │    ├─ media_summaries
  │    ├─ media_chapters
  │    ├─ media_processing_attempts
  │    └─ media_export_records
  ├─ evaluation_datasets
  │    ├─ evaluation_cases
  │    └─ evaluation_runs
  │         └─ evaluation_results
  └─ user_feedback

users (account authentication; no ownership relationship to content tables)
```

A processed media source can point to one transcript-backed `documents` row through `media_sources.transcript_document_id`. This makes transcript chunks available to the same retrieval engine. The database uses `SET NULL` for that link (`backend/app/models/media.py:68-70`), while media deletion logic can explicitly remove derived content.

## All 19 tables

### 1. `knowledge_bases`

- **Model:** `KnowledgeBase`, `backend/app/models/knowledge_base.py:14-30`.
- **Important columns:** UUID `id`, indexed `name`, optional `description`; timestamp and lifecycle fields from both mixins.
- **Relationships:** Parent of documents and chat sessions in the ORM; media/evaluation/feedback also reference its ID by foreign key.
- **Used by:** Knowledge, dashboard, workspace ID, source library, chat, video, intelligence, evaluation, feedback, cleanup, demo seed.
- **Deletion:** Child document/chat relationships declare database/ORM cascade. No public KB delete route currently exists.

### 2. `documents`

- **Model:** `Document`, `backend/app/models/document.py:47-108`.
- **Important columns:** KB ID, name/type/media type/size/checksum/storage key, detailed processing status/message/error/warnings/metadata, extracted text, page/character/chunk/index counts, attempts/model, processing/extraction/index timestamps, lifecycle fields.
- **Constraints:** One checksum per KB; globally unique storage key; status indexes.
- **Relationships:** KB parent; sections/chunks cascade; optional reverse media transcript link.
- **Used by:** upload/processing/detail/library/dashboard/RAG/intelligence/evaluation/media transcript index/cleanup.

### 3. `document_sections`

- **Model:** `DocumentSection`, `backend/app/models/document.py:111-129`.
- **Important columns:** stable ID, document ID, section index, optional page/heading, text, start/end character, JSON metadata.
- **Constraint:** document ID plus section index is unique.
- **Used by:** extraction detail and section summaries; deleted with document.

### 4. `document_chunks`

- **Model:** `DocumentChunk`, `backend/app/models/document.py:132-160`.
- **Important columns:** document/KB IDs, order, text/location/character/token data, JSON extraction metadata, raw embedding bytes, dimension/model/index timestamp.
- **Constraint/indexes:** unique order per document; KB/indexed lookup index.
- **Used by:** document detail, custom vector search, hybrid reranking, RAG, citations, intelligence, evaluation, media Q&A.

### 5. `chat_sessions`

- **Model:** `ChatSession`, `backend/app/models/conversation.py:20-35`.
- **Important columns:** UUID, KB ID, title, created/updated.
- **Relationships:** KB parent; ordered messages cascade on session deletion.
- **Used by:** Research chat list/open/delete and conversation history.

### 6. `chat_messages`

- **Model:** `ChatMessage`, `backend/app/models/conversation.py:38-56`.
- **Important columns:** session ID, role, content, original/rewritten query, JSON citations, JSON model metadata, JSON verification, timestamps.
- **Used by:** Chat history, query rewrite context, evidence replay.

### 7. `users`

- **Model:** `User`, `backend/app/models/user.py:26-42`.
- **Important columns:** unique indexed email, bcrypt password hash, name, role, active flag, timestamps.
- **Used by:** accounts-mode registration/login only.
- **Important gap:** No user foreign key exists on KBs, documents, media, chats, feedback, or evaluations. Accounts do not create tenant data isolation.

### 8. `media_sources`

- **Model:** `MediaSource`, `backend/app/models/media.py:53-126`.
- **Important columns:** KB/transcript document IDs, source kind/URL/storage/name/type/size/checksum/platform/title/author/duration/language/thumbnail/subtitle; transcription and detailed processing status/progress/warnings/metadata; safe and technical errors, retry flag, attempts/dates, lifecycle.
- **Constraints:** checksum per KB; unique storage key; one transcript document per media source.
- **Used by:** source library, video detail, processing, media Q&A, cleanup.
- **Security:** `technical_error_message` is stored for operators but is omitted from normal media response schemas.

### 9. `transcript_jobs`

- **Model:** `TranscriptJob`, `backend/app/models/media.py:129-149`.
- **Important columns:** media ID, queued/running/complete/failed status, model/device/compute type/languages, attempt/error/timestamps.
- **Used by:** processing history and media detail.

### 10. `transcript_segments`

- **Model:** `TranscriptSegment`, `backend/app/models/media.py:152-172`.
- **Important columns:** media/job IDs, ordered index, start/end seconds, text, language, confidence.
- **Constraint:** media ID plus segment index is unique.
- **Used by:** transcript reader/search/player synchronization, transcript index, media exports and intelligence.

### 11. `media_summaries`

- **Model:** `MediaSummary`, `backend/app/models/media.py:175-190`.
- **Important columns:** media ID, summary kind, content, JSON structured data, model name.
- **Constraint:** one kind per media source.
- **Used by:** Video intelligence and summary export.

### 12. `media_chapters`

- **Model:** `MediaChapter`, `backend/app/models/media.py:193-209`.
- **Important columns:** media ID, order, start/end, title, summary.
- **Constraint:** media ID plus chapter index is unique.
- **Used by:** Video chapter timeline/intelligence.

### 13. `media_processing_attempts`

- **Model:** `MediaProcessingAttempt`, `backend/app/models/media.py:212-226`.
- **Important columns:** media ID, attempt number, start/completion, final stage, success, error code.
- **Used by:** safe retry history in media detail.

### 14. `media_export_records`

- **Model:** `MediaExportRecord`, `backend/app/models/media.py:229-239`.
- **Important columns:** media ID, export kind, format, timestamps.
- **Used by:** audit that an export was requested; exported bytes remain generated on request.

### 15. `evaluation_datasets`

- **Model:** `EvaluationDataset`, `backend/app/models/evaluation.py:22-38`.
- **Important columns:** KB ID, name/description, denormalized case count, creation time.
- **Used by:** benchmark API/page and feedback conversion.

### 16. `evaluation_cases`

- **Model:** `EvaluationCase`, `backend/app/models/evaluation.py:41-57`.
- **Important columns:** dataset ID, question, optional expected answer/citation IDs, language, supported flag, created time.
- **Used by:** RAG benchmark execution.

### 17. `evaluation_runs`

- **Model:** `EvaluationRun`, `backend/app/models/evaluation.py:60-83`.
- **Important columns:** dataset, engine/model, total/pass/fail, correctness/faithfulness/citation rates, median/p95 latency, creation time.
- **Used by:** evaluation history and export.

### 18. `evaluation_results`

- **Model:** `EvaluationResult`, `backend/app/models/evaluation.py:86-101`.
- **Important columns:** run ID, case ID string, pass flag, generated answer, verification, returned citation IDs, latency, error.
- **Relationship note:** `run_id` is a cascading foreign key. `case_id` is not declared as a foreign key, so the database cannot enforce that it still names a case.
- **Used by:** persisted per-case benchmark result; current frontend only shows aggregate runs.

### 19. `user_feedback`

- **Model:** `UserFeedback`, `backend/app/models/feedback.py:20-39`.
- **Important columns:** KB ID, optional chat message ID, question/answer, helpful/unhelpful rating, category/comment, engine/model/latency, optional converted-case ID, created time.
- **Relationship note:** KB is a foreign key. Chat message and converted case are plain IDs without foreign keys.
- **Used by:** feedback submission/analytics/conversion APIs and analytics page.

## Shared lifecycle fields

`TimestampMixin` adds `created_at` and `updated_at` (`backend/app/db/base.py:15-21`). `DemoLifecycleMixin` adds:

- `last_accessed_at` — updated when a lifecycle-managed record is used.
- `expires_at` — nullable deletion eligibility time.
- `is_protected` — cleanup exemption.

The lifecycle mixin is used by knowledge bases, documents, and media. Cleanup also protects active children and a protected parent (`backend/app/services/cleanup.py:69-168`). It does not automatically run inside FastAPI; the tracked systemd timer invokes the cleanup script hourly (`deploy/systemd/enterprise-rag-cleanup.timer:4-8`).

## Migration history

| Revision | File | What it introduces |
|---|---|---|
| `0001_phase1_baseline` | `backend/migrations/versions/0001_phase1_baseline.py` | Users, knowledge bases, initial documents, indexes/constraints. |
| `0002_processing_rag_intelligence` | `backend/migrations/versions/0002_processing_rag_intelligence.py` | Detailed document processing data, sections/chunks, conversations/messages. |
| `0003_media_intelligence` | `backend/migrations/versions/0003_media_intelligence.py` | Media sources, transcript jobs/segments, summaries, chapters, attempts, exports. |
| `0004_public_demo_lifecycle` | `backend/migrations/versions/0004_public_demo_lifecycle.py` | Demo lifecycle columns/indexes and evaluation/feedback tables. |

The expected head is the fourth migration. Application lifespan also calls `Base.metadata.create_all` (`backend/app/main.py:66-72`), which helps fresh development databases, but operators should still run Alembic so `alembic_version` accurately proves migration history. Production startup calls `backend/scripts/migrate_database.py` before Uvicorn (`start-space.sh:9-15`).

## Safe inspection

Stop or use a read-only copy when doing substantial inspection. Never edit a production SQLite file with an ad-hoc client.

```bash
# Development: show migration revision.
cd backend
.venv/bin/alembic current
.venv/bin/alembic heads

# Read-only SQLite inspection. Replace the path only after confirming it.
sqlite3 -readonly data/enterprise_rag.db '.tables'
sqlite3 -readonly data/enterprise_rag.db \
  "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
sqlite3 -readonly data/enterprise_rag.db \
  "SELECT version_num FROM alembic_version;"

# Counts expose no source text, but still run only where authorized.
sqlite3 -readonly data/enterprise_rag.db \
  "SELECT 'knowledge_bases', count(*) FROM knowledge_bases UNION ALL SELECT 'documents', count(*) FROM documents UNION ALL SELECT 'media_sources', count(*) FROM media_sources;"
```

Inside the AWS container, use a backup or run only a read-only query against `/data/enterprise_rag.db`. The production backup script is safer than copying a live SQLite file because it invokes a SQLite-aware backup path (`scripts/backup-production.sh`).

## Confirm migrations are current

1. Back up the database before any migration on an important environment.
2. Run `cd backend && .venv/bin/alembic current` locally, or the migration script in the same container environment.
3. Confirm current revision equals `0004_public_demo_lifecycle` and `alembic heads` shows the same single head.
4. Call `/api/v1/readiness`. Its `_schema_is_current` check reads the migration state and fails readiness when it is stale (`backend/app/api/routes/health.py:35-81`).
5. Run backend database/API tests in a disposable database.

Do not run `alembic downgrade`, delete `alembic_version`, or directly modify tables as a troubleshooting shortcut.
