# 09 — Limitations and risks

This is an evidence-based review, not a penetration test, legal opinion, capacity test, or guarantee. Items are ordered roughly from product behavior to operations.

## Product and UI gaps

| Limitation or risk | Evidence and effect | Practical response |
|---|---|---|
| Knowledge bases cannot be edited or deleted through the product. | Routes only create/list/get (`backend/app/api/routes/knowledge_bases.py:32-76`); `KnowledgeBasesPage` only creates/opens (`frontend/src/pages/KnowledgeBasesPage.tsx`). A quota error can therefore be hard for users to resolve. | Let expiry cleanup remove demo collections or add an authorized delete/edit design later. Do not delete DB rows manually. |
| Workspace is mostly a static navigation card. | `WorkspacePage.tsx:12-50` never calls the KB detail API, displays a generic title, and routes many tabs to shared pages. A fake ID renders the same UI. | Treat it as a shortcut only. Validate collection data on destination pages. |
| Workspace validation remains partial. | Source, Chat, and Intelligence honor the scoped ID and named routes are correct, but `WorkspacePage` does not fetch/validate the ID or show the collection name. | Treat it as a shortcut. Add a detail fetch plus not-found state in a future focused change. |
| Feedback is not collectable from normal UI. | API/client can submit and convert (`frontend/src/api/client.ts:486-526`), but Chat has no rating control and `FeedbackPage.tsx` only displays analytics. | Use API for controlled evaluation or add a visible privacy-aware rating/conversion flow. |
| Evaluation data cannot be created from the Evaluation page. | Page imports only list/run functions (`EvaluationPage.tsx:1-3`). Create dataset/case routes exist in `backend/app/api/routes/evaluation.py:71-120`. | Seed or call API first. Add editor/validation UX later. |
| Media delete is API-only. | `DELETE /media/{id}` exists (`backend/app/api/routes/media.py:522-531`), but `client.ts` and Video/Upload pages have no deleteMedia action. | Use authorized API/operator flow; add confirmation UI later. |
| Demo seed is API-only. | `seedDemoWorkspace` exists (`frontend/src/api/client.ts:468-470`) but no page calls it. | Use curl in disposable/demo data or add an explicit protected setup action. |
| Chat cancellation is visual only. | Pending UI shows `CircleStop`, but no AbortController/click handler is attached (`frontend/src/pages/ChatPage.tsx:413-419`). | Wait for the bounded client/server timeout. Add real abort/cancellation as a product feature. |
| “Regenerate” is not automatic. | It sets the composer to “Answer again more concisely.” (`ChatPage.tsx:393-395`) and does not submit. | User must review and submit. Rename or implement explicit regenerate later. |
| Sidebar recent items are presentation-only. | Recent labels are fixed links in `AppShell.tsx`, not data-backed history. | Label them as shortcuts or replace them with a real recent-query API before presenting them as activity. |
| Templates do not enforce their advertised output schema. | Templates contain `output_schema_type` (`backend/app/services/templates.py:9-18`) but Run Workflow sends an ordinary chat prompt (`TemplatesPage.tsx:89`). | Treat as prompt starters, not guaranteed structured workflows. |
| Document intelligence output is not persisted. | Summary/comparison/report APIs return schemas but there is no corresponding model/table. Frontend report download is client-side. | Save exports immediately if needed; design result persistence/audit separately. |

## Authentication, authorization, and security boundaries

| Limitation or risk | Evidence and effect | Practical response |
|---|---|---|
| Accounts mode is not multi-tenant authorization. | `users` has no relationship to KB/document/media/chat/evaluation/feedback. Data routes query by global IDs without owner scope. | Use accounts mode only for a shared workspace unless row ownership/authorization is implemented. Do not host mutually untrusted tenants. |
| `/auth/me` is not a full account lookup. | Handler returns a synthetic demo email/name with principal role (`backend/app/api/routes/auth.py:241-248`) rather than loading `users`. | Do not use it as authoritative account profile/state. |
| Admin role has no verified admin controls. | `UserRole.ADMIN` exists (`backend/app/models/user.py:13-15`), but no admin page or admin-only route check was found. | Do not claim admin management. Implement explicit authorization before exposing admin operations. |
| Limits and heavy queue are process-local. | Middleware limiter and `GenerationQueue` live in application state (`backend/app/main.py:107-110,183-201`). Multiple workers/containers do not share counters/slots. | Keep one worker/container or move limits/jobs to a shared durable service before scaling. |
| No malware scanner exists. | Validation checks type/signature/content/path, but no antivirus/sandbox integration appears in dependencies/services. | Do not accept untrusted high-risk uploads in a sensitive network; add scanning/quarantine for production. |
| Legal notices are not compliance evidence. | `LegalPage.tsx` is static project text. No SOC 2, ISO, GDPR process/certification artifacts are in code. | Obtain legal/security review for the actual deployment and data class. |
| Container runs as default image user. | `Dockerfile` contains no `USER` directive. Compose drops capabilities and sets no-new-privileges, but the process can still be root inside the container. | Consider a tested non-root image and writable-volume permissions in a future hardening change. |
| Technical media errors are stored. | `media_sources.technical_error_message` exists (`backend/app/models/media.py:97-100`) although response schemas omit it. | Restrict DB/backups/operator logs; preserve response sanitization; never store cookie text. |
| Content persists in DB/files/backups. | Extracted text, transcripts, questions, answers, citations, and feedback are model columns. Cleanup and backup retention differ. | Do not upload confidential/personal/regulated data to the public demo; secure and expire backups separately. |

The code includes useful protections: signed HttpOnly sessions, bcrypt, same-origin cookie checks, CORS, request/body/upload limits, URL/redirect validation, safe storage resolution, CSP/security headers, structured errors, and cookie redaction. These reduce risk; they do not replace a deployment-specific security assessment.

## YouTube and remote media

| Limitation or risk | Evidence and effect | Practical response |
|---|---|---|
| YouTube success cannot be guaranteed. | Landing and AWS guide explicitly describe best-effort URL handling and direct-upload fallback (`LandingPage.tsx:65-67,124`; `docs/aws-cpu-deployment.md:14-32,67-72`). YouTube changes challenge/format/auth behavior. | Prefer permitted direct MP3/MP4. Keep yt-dlp/Deno current through reviewed releases. |
| Cloud/AWS IPs may be blocked or challenged. | Product notice warns about cloud-hosted IP rejection. Runtime can safely classify challenge/no-format/auth failures but cannot change platform policy. | Test on the actual host; do not retry forever; use an authorized alternative source. |
| Cookies expire and are sensitive. | Host cookie is mounted read-only and copied to mode 0600 before use (`backend/app/services/media.py:197-245`; `docker-compose.aws.yml:21`). | Rotate atomically from a trusted workstation, restrict file/backup/log access, and never send contents to frontend/issues. |
| Deno does not solve every case. | Docker adds a supported runtime (`Dockerfile:13-21`) and code checks availability, but PO Tokens or account/region/age rules may still apply. | Return the existing terminal actionable error; use an approved PO-token provider only if operator policy allows, or direct upload. |
| Remote downloads are dependent on third parties. | URL validation and timeouts are implemented, but host availability, redirects, media formats, licenses, and terms can change. | Use only content you may access; preserve SSRF validation; keep bounded timeouts. |

## Model quality, compute, and AI behavior

| Limitation or risk | Evidence and effect | Practical response |
|---|---|---|
| Local model quality is bounded. | Default is a 0.5B Qwen model with FLAN/extractive fallback (`config.py:71-72`; provider). Small models can miss nuance or formatting. | Verify citations, use evaluation datasets, choose a larger model only where hardware supports it. |
| Cold start/download can be slow or fail. | Providers are lazy and can download unless `hf_local_files_only=true`; AWS starts cold (`docs/aws-cpu-deployment.md:74-77`). | Pre-cache during controlled provisioning, warm explicitly, monitor disk/RAM, keep UI timeouts. |
| AWS CPU profile trades quality/context for memory. | Profile forces CPU, 96 max new tokens, 3000 context, serial work, smaller batches (`backend/app/core/config.py:255-273`). | Keep expectations and source scope small; use queue feedback; measure on real host. |
| Quantization is not an AWS CPU feature. | `resolve_quantization` creates BitsAndBytes configs only for supported CUDA; CPU/MPS fall back (`backend/app/ai/quantization.py:21-68`). | Leave `none` on CPU. Test CUDA 4/8-bit separately with supported hardware/packages. |
| Verification is heuristic by default. | `verification_mode=deterministic` and `VerificationService` uses token/source rules. | Treat badge as support assistance, not proof. Read cited passages. |
| Evaluation correctness is simple token coverage. | `_answer_coverage` is word-set overlap and threshold is 0.5 (`backend/app/services/evaluation.py:26-31,131-136`). | Use benchmark trends, not absolute semantic quality; review cases/results manually. |
| Media intelligence is deterministic heuristics. | `TranscriptIntelligenceService` (`backend/app/media/intelligence.py:57`) creates outputs without a full generative analysis call. | Expect approximate entities/actions/chapters; verify against transcript. |
| No speaker diarization. | Transcript segments have timestamps/text/language/confidence but no speaker column (`backend/app/models/media.py:152-170`). | Do not claim speaker attribution; add a diarization pipeline/schema if required. |
| Model save/reload and LoRA are not production workflows. | `model_io.py` helpers and `course_demo/fine_tuning/` exist, but `main.py` does not call fine-tuning and normal providers load configured models. | Treat as learning/experimental. Do not promise product training on uploads. |

## Data, database, storage, and scale

| Limitation or risk | Evidence and effect | Practical response |
|---|---|---|
| SQLite is a single-instance design. | Default/AWS database is one SQLite file; deployment runs one container (`docs/deployment.md:3-16`). Concurrent writes/replicas and failover are limited. | Keep one app instance; back up; migrate deliberately to PostgreSQL/shared storage for scale. |
| Relational vector search scans a small local corpus. | `RelationalVectorStore` stores bytes in `document_chunks`; no pgvector/service is configured. | Keep demo corpus/quotas bounded; use FAISS optional path or a production vector DB for large data. |
| LangChain FAISS is separate persistence. | Index lives under `langchain_index_path` with embedding model identity checks (`document_pipeline.py`). Switching engine/model requires reindex. | Persist the index path and reprocess sources after changes; do not mix embeddings. |
| Alembic does not reproduce all ORM tables by itself. | A fresh upgrade to `0004_public_demo_lifecycle` creates 13 application tables; `users`, four evaluation tables, and `user_feedback` appear only when `Base.metadata.create_all` runs at application startup (`backend/app/main.py:66-72`). Readiness checks only selected schema elements. | Keep normal startup in the deployment path. Design and rehearse an adoption-safe migration for the six tables before removing `create_all` or using migration-only provisioning. |
| File and DB consistency can be interrupted. | Processing spans filesystem, database, model, and background task steps. Code records failure/attempts and cleanup removes orphans later, but it is not one cross-system transaction. | Use retries/status/cleanup; monitor storage; back up both DB and files together. |
| Lifecycle cleanup depends on external timer. | Service exists but FastAPI does not schedule it; systemd timer must be installed/enabled. | Verify timer and operation marker. Run dry-run after configuration changes. |
| Backup contains source content and is local. | Backup includes SQLite/uploads and is bound to a host directory. No built-in off-site/encryption service. | Apply host permissions, encrypted/off-site copy policy, restore drills, and separate retention. |
| Upload/context/duration/timeouts are deliberately bounded. | Settings default to 50 MB, 300 pages, 30 minutes, and finite generation/media timeouts (`backend/app/core/config.py:50-64,141-155`). | Split sources, use direct smaller media, narrow report scope, and do not raise limits without capacity/security testing. |

## Deployment and operations

| Limitation or risk | Evidence and effect | Practical response |
|---|---|---|
| Live DuckDNS/domain/certificate is not repository state. | No DuckDNS references; Nginx has `demo.example.com` and HTTP only. Certbot changes installed host config. | **Not verified from the current codebase.** Validate DNS/IP/cert/renewal/firewall on the host. |
| Health is not readiness. | Docker healthcheck calls lightweight `/health` (`docker-compose.aws.yml:23-28`); `/readiness` checks DB/schema/paths. | Monitor both. An “up” container can still have stale schema/unwritable storage/model problems. |
| Health does not load models. | Models are cold by default; liveness intentionally avoids download. | Check `/rag/config`, warm in a controlled window, and test a real answer after deploy. |
| Rollback image does not automatically reverse data. | Deploy script restores prior image on failed health, while restore is a separate explicit workflow. | Use verified backup when a schema/data rollback is required. Never delete named volumes. |
| Host paths are opinionated. | systemd/scripts assume `/home/ubuntu/EnterpriseRAG`, cookie and backup paths. | Review/edit templates safely before installing elsewhere; validate Compose expansion. |
| Space defaults are ephemeral. | Dockerfile uses `/tmp` database/uploads/models for Hugging Face profile (`Dockerfile:58-66`). | Add supported persistence if platform requires it; do not assume `/tmp` durability. |
| No built-in metrics/alerting stack. | Operations status/logs/systemd checklist exist; no Prometheus/OpenTelemetry/alert manager dependency. | Use host/cloud monitoring and alerts appropriate to the deployment. |

## Test coverage limitations

- There are 35 automated test files, including 13 frontend unit-test files. Several major pages still rely mostly on Playwright/backend coverage.
- Real Hugging Face and transcription tests are intentionally excluded from deterministic CI via registered markers (`backend/pyproject.toml:63-70`; `.github/workflows/ci.yml:28-29`). CI therefore does not prove current external model access.
- Public YouTube success cannot be deterministic in CI. Tests validate option construction, cookie safety, and failure classification instead.
- Backup tests verify scripts in controlled fixtures; an actual host restore, DNS, firewall, Certbot renewal, cloud snapshot, and disk exhaustion behavior require deployment testing.
- Load/capacity, accessibility audit, cross-browser matrix, formal security penetration testing, and legal/compliance testing are **Not verified from the current codebase.**

## “Likely broken” versus “partial”

The audit found no remaining confirmed compile/runtime break in the inspected product paths after correcting the workspace Evaluation route and Intelligence scoping. Feedback collection, evaluation creation, media deletion, demo seeding, chat cancellation, and dynamic recent activity remain partial/missing UI rather than broken backend features.
