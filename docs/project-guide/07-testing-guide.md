# 07 — Testing guide

Run tests against disposable data unless a step explicitly belongs to a controlled production-validation window. Never use real confidential documents, real passwords in commands, or a live backup as a test fixture.

## One-time local setup

Preconditions: Python 3.11+, Node 20+, npm, ffmpeg, Poppler, and Tesseract. Media transcription also needs the `media` extra. The existing local `backend/.venv` can be reused if it is healthy.

```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/pip install -e 'backend[dev,media]'
npm ci --prefix frontend
```

On macOS, install system binaries through the package manager you trust. On CI Ubuntu, `.github/workflows/ci.yml:18-25` installs ffmpeg, Poppler, and Tesseract before the Python package.

## Fast smoke checklist

**Preconditions:** Disposable database/storage, backend started, models cached or deterministic test server, and access credentials for the selected mode.

**Steps:**

1. `curl -i http://127.0.0.1:7860/api/v1/health` -> expect 200.
2. `curl -i http://127.0.0.1:7860/api/v1/readiness` -> expect 200 and all checks ready.
3. Open `/`, then `/login`, authenticate, and open `/dashboard`.
4. Create a KB, upload a small TXT, wait for ready, open detail, and inspect chunks.
5. Ask an answerable question and an unsupported question. Confirm citations for the first and safe not-found behavior for the second.
6. Upload a short permitted MP3, wait for ready, inspect/search transcript, ask a media question, and download one export.
7. Generate a short summary. Open every sidebar destination and refresh one dynamic URL directly.

**Expected result:** No endless spinner, console error, failed same-origin API path, auth loop, or server 500. Errors terminate with an actionable message.

**Relevant files:** `frontend/e2e/production-smoke.spec.ts`; `backend/tests/test_policy_e2e.py`; route/page/service files in the preceding guides.

## CI-equivalent automated checks

These are the exact backend checks in `.github/workflows/ci.yml:22-29`, with the backend script directory included in Ruff:

```bash
backend/.venv/bin/pip install -e 'backend[dev,media]'
backend/.venv/bin/ruff check backend/app/ backend/tests/ backend/scripts/ course_demo/
backend/.venv/bin/pytest backend/tests/ -v -m "not real_models and not real_transcription"
```

The exact frontend checks are:

```bash
npm ci --prefix frontend
npx --prefix frontend tsc --noEmit
npm run build --prefix frontend
npm run test --prefix frontend
```

**Expected result:** Every command exits 0. Marker filtering must use `-m`, not name filtering. Markers are registered at `backend/pyproject.toml:63-70`.

## Frontend unit and build tests

**Preconditions:** `npm ci --prefix frontend` completed.

**Steps and expected results:**

1. `npm run typecheck --prefix frontend` — no TypeScript errors.
2. `npm run build --prefix frontend` — production files appear under `frontend/dist/`; production client contains same-origin `/api/v1`, not a development host.
3. `npm run test --prefix frontend` — all 13 unit-test files pass.

**Coverage:**

- API timeout, error, auth-event behavior: `frontend/src/api/client.test.ts`.
- Citation and status rendering: `CitationList.test.tsx`, `StatusBadge.test.tsx`.
- Chat answer/error/mode behavior: `ChatPage.test.tsx`.
- Bounded document polling: `DocumentPage.test.tsx`.
- Login error/loading/token behavior: `LoginPage.test.tsx`.
- Settings terminal load failure: `SettingsPage.test.tsx`.
- Workspace route/scoping behavior: `WorkspacePage.test.tsx`, `IntelligencePage.test.tsx`.
- API-backed source readiness and feedback loading: `DashboardPage.test.tsx`, `FeedbackPage.test.tsx`.
- Non-interactive current-workspace status semantics: `AppShell.test.tsx`.
- Arabic direction helper: `utils/language.test.ts`.

**Known coverage gap:** Knowledge Bases, Upload, Video, Evaluation, Templates, Landing, and Legal do not each have a dedicated unit-test file. Browser/backend tests cover parts of them.

## Deterministic Playwright tests

**Preconditions:** Backend virtual environment installed, frontend npm dependencies installed, Chromium installed with `npx --prefix frontend playwright install chromium`. Ports 8010 and the configured development port must be free.

```bash
npm run test:e2e --prefix frontend
```

The Playwright config starts `backend/.venv/bin/python -m scripts.run_test_server` and Vite automatically (`frontend/playwright.config.ts:23-39`).

**Expected result:**

- `enterprise-rag.spec.ts` completes document RAG, local media, responsiveness/error boundaries, and deterministic public media URL paths.
- The production smoke spec's applicable mocked/deterministic paths terminate with no browser console or unexpected network errors.
- Failure artifacts go to `artifacts/playwright-report` and retained trace/screenshot/video paths (`frontend/playwright.config.ts:13-18`).

## Backend tests

**Preconditions:** Python extras and system binaries installed. No real-model flag is required for deterministic tests.

```bash
backend/.venv/bin/pytest backend/tests/ -v -m "not real_models and not real_transcription"
```

**Expected result:** All selected tests pass; three real-model/transcription files remain collected but deselected as appropriate. Important groups:

- CRUD/processing: `test_knowledge_bases.py`, `test_documents.py`, `test_processing.py`.
- RAG/intelligence/language: `test_rag.py`, `test_intelligence.py`, `test_multilingual.py`.
- Media: `test_media.py` with fake transcription and deterministic yt-dlp/cookie failure tests.
- Evaluation/feedback: `test_evaluation.py`.
- Runtime: `test_ai_providers.py`, `test_hardware.py`, `test_low_memory.py`.
- Auth/limits/cleanup/policy: `test_public_demo_auth.py`, `test_public_demo_limits_cleanup.py`, `test_policy_e2e.py`.
- Health and maintenance: `test_health.py`, `test_backup_restore.py`.
- Direct LangChain/course integration: `test_langchain_course_layer.py`.

`backend/tests/conftest.py` provides temporary paths/database and fake models so deterministic CI does not download remote weights.

## Real model and transcription tests

These tests remain manually runnable; do not remove them or fold them into network-free CI.

```bash
# See what would run without executing it.
backend/.venv/bin/pytest backend/tests/ --collect-only -q -m real_models
backend/.venv/bin/pytest backend/tests/ --collect-only -q -m real_transcription

# Run only in an authorized environment with enough disk/RAM and model access.
RUN_REAL_MODEL_TESTS=1 backend/.venv/bin/pytest backend/tests/ -v -m real_models
RUN_REAL_TRANSCRIPTION_TESTS=1 backend/.venv/bin/pytest backend/tests/ -v -m real_transcription
```

**Expected result:** Hugging Face custom and LangChain paths retrieve/parse real output; faster-whisper transcribes the provided local sample. Relevant files are `test_real_huggingface_rag.py`, `test_real_langchain_rag.py`, and `test_real_transcription.py`.

**Failure interpretation:** A missing/corrupt cache, unavailable remote model, disk/RAM shortage, or no network is an environment failure, not permission to weaken assertions.

## API tests

**Preconditions:** Running disposable app and authentication cookie/token. Use the safe setup in [API reference](04-api-reference.md).

**Steps:**

1. Call each public health/auth endpoint signed out; protected data endpoints should return 401 in protected modes.
2. Authenticate and run the curl examples in the API guide group by group.
3. For every POST, test valid data, missing required data, wrong types, unknown parent ID, and limit violations.
4. For process endpoints, confirm 202 then poll to ready/failed; for delete, confirm 204 then 404 on get.
5. Capture `X-Request-ID` on failures and confirm the JSON error has a stable code/message but no internal path/trace/cookie.

**Expected result:** Exactly the documented success shape/status; predictable 4xx for client errors; no secret leakage.

**Relevant tests/files:** All `backend/tests/test_*.py`; handlers under `backend/app/api/routes/`; schemas under `backend/app/schemas/`.

## Database and migration tests

**Preconditions:** Disposable database or read-only copy. Back up before a real migration.

```bash
cd backend
.venv/bin/alembic heads
.venv/bin/alembic current
.venv/bin/alembic upgrade head
cd ..
curl -i http://127.0.0.1:7860/api/v1/readiness
```

**Steps:** Confirm the single head/current revision is `0004_public_demo_lifecycle`; on a disposable database compare the tables immediately after `alembic upgrade head` with `Base.metadata.tables`; then start the app and inspect all 19 table names read-only. Create parent/child test data; delete a document/session/media through API and verify intended cascades; do not manually delete rows.

**Expected result:** Migration succeeds and normal startup/readiness/tests work. Record the known six-table migration-only coverage gap rather than treating the head revision as complete schema proof; foreign-key/cascade behavior should match the model guide.

**Relevant files:** `backend/migrations/`; `backend/app/models/`; `backend/tests/test_health.py`, `test_documents.py`, `test_media.py`.

## Upload and processing tests

**Preconditions:** Empty test KB, system PDF/OCR/media tools, small non-sensitive fixtures.

**Steps:**

1. Upload valid TXT/PDF/DOCX; expect 201.
2. Start/auto process; poll; expect extraction sections, preview, chunks, equal ready/index counts.
3. Try renamed binary, corrupt PDF/DOCX, duplicate checksum, too many pages/files, oversized/chunked body, and unsafe filename.
4. Test text PDF, scanned OCR PDF, Arabic scan, and PDF table.
5. Stop a poll or force a slow fake task; verify UI has a bounded timeout and server status can be refreshed later.

**Expected result:** Valid input reaches ready; invalid input returns a safe terminal error and does not escape storage or leave an endless UI state.

**Relevant files/tests:** Upload/Document pages; `test_documents.py`, `test_processing.py`, `test_policy_e2e.py`, `DocumentPage.test.tsx`.

## Search, RAG answer, and citation tests

**Preconditions:** Two known small documents with overlapping and unique facts, fully indexed.

**Steps:** Call `/retrieve` for exact keyword and paraphrase; inspect scores/diversity. Ask a known fact, a follow-up pronoun question, a contradiction, and an unknown fact. Test source-document filtering and Arabic/English output. Follow every citation to its chunk/page.

**Expected result:** Known answer uses only evidence and citations; unknown answer has `not_found=true`/unsupported behavior and no invented source; history rewrite is visible in debug; duplicate chunks do not dominate.

**Relevant files/tests:** `test_rag.py`, `test_multilingual.py`, `test_policy_e2e.py`, `ChatPage.test.tsx`, `CitationList.test.tsx`; optional real-model tests.

## Media and YouTube tests

**Preconditions:** ffmpeg/ffprobe; direct short MP3/MP4; fake provider for deterministic suite. Network tests require authorization, Deno, current yt-dlp, permitted URL, and private cookie handling.

**Steps:**

1. Upload direct MP3/MP4; expect ready transcript/segments/intelligence/index.
2. Search transcript, seek a timestamp, ask media, and download all four exports.
3. Test invalid signature, oversized/over-duration file, retry, and deletion via API.
4. Test private/loopback URL and redirect; expect rejection.
5. Confirm read-only cookies are copied to 0600 writable runtime file, refresh by mtime, and never appear in logs.
6. In container run `deno --version`; classify expired-cookie, n-challenge, PO-token, and no-format failures as safe terminal errors.

**Expected result:** Direct media works locally. Remote failures terminate with action text and no path/cookie detail. YouTube success is environment-dependent.

**Relevant files/tests:** `backend/tests/test_media.py`, optional `test_real_transcription.py`, `frontend/e2e/enterprise-rag.spec.ts`.

## Intelligence and evaluation tests

**Preconditions:** Ready document(s); evaluation additionally needs a dataset/cases created through API/demo seed.

**Steps:** Run short/detailed/section summaries, two-document comparison, report, languages, timeout and partial paths. Create supported/unsupported evaluation cases, run, inspect stored totals/rates/latency, and export page Markdown.

**Expected result:** Structured grounded output with citations/verification; comparison enforces two documents; report marks partial results; evaluation metrics match stored case outcomes.

**Relevant files/tests:** `test_intelligence.py`, `test_evaluation.py`, `test_multilingual.py`, `test_low_memory.py`; Intelligence/Evaluation pages.

## Authentication and security checks

**Preconditions:** Disposable instances for `open`, `demo_password`, and `accounts`; HTTPS/proxy test for secure cookie behavior.

**Steps:** Test public/protected route matrix, wrong/correct password, lockout, register/login/logout, tampered/expired token, inactive account, malicious `next`, cross-origin unsafe cookie request, bearer request, body/rate limits, path traversal filenames/content URLs, SSRF URL classes, security headers, and log redaction.

**Expected result:** No auth loop; protected data denied when unsigned; cookie is HttpOnly/SameSite and Secure in HTTPS config; cross-site unsafe requests denied; no secret/technical path in frontend response/log.

**Relevant files/tests:** `test_public_demo_auth.py`, `test_policy_e2e.py`, `test_public_demo_limits_cleanup.py`; Login test; Nginx template.

## Backup and restore tests

**Preconditions:** Disposable Compose deployment, writable dedicated backup directory, known sample KB/file, enough disk. Never point this exercise at a directory outside the configured backup root.

```bash
ENTERPRISE_RAG_BACKUP_DIR=/absolute/disposable/backups scripts/backup-production.sh
scripts/verify-backup.sh /absolute/disposable/backups/<backup-directory>
scripts/restore-production.sh /absolute/disposable/backups/<backup-directory> --confirm
```

**Steps:** Record sample data/checksum; back up and verify; change/delete sample; restore with explicit confirmation; health/readiness and data/file checks; inspect secret-free environment template and private permissions. Corrupt a copy of a checksum/file and confirm verification refuses it.

**Expected result:** Verified original data returns; corrupt/wrong-scope backup is rejected; a pre-restore backup exists; service restarts healthy.

**Relevant files/tests:** `scripts/backup-production.sh`, `verify-backup.sh`, `restore-production.sh`, `backend/tests/test_backup_restore.py`.

## Docker and production browser tests

**Preconditions:** Docker running, unused port 7865, safe local env file, Chromium installed. Do not alter Docker Desktop data/settings as part of this test.

```bash
docker build -t enterprise-rag:production-test .
docker run --rm --name enterprise-rag-production-test \
  -p 7865:7860 \
  enterprise-rag:production-test
```

In another terminal:

```bash
curl -i http://127.0.0.1:7865/
curl -i http://127.0.0.1:7865/api/v1/health
curl -i http://127.0.0.1:7865/dashboard
docker exec enterprise-rag-production-test deno --version

PLAYWRIGHT_BASE_URL=http://127.0.0.1:7865 \
PLAYWRIGHT_PRODUCTION=1 \
npm run test:e2e --prefix frontend -- production-smoke.spec.ts
```

**Expected result:** Image builds with its disposable `/tmp` profile; startup migrates; `/`, assets, API, and direct SPA routes work; production API requests stay under same-origin `/api/v1`; no console/network/auth/loading failure; Deno is 2.3+.

**Relevant files:** `Dockerfile`, `start-space.sh`, `frontend/e2e/production-smoke.spec.ts`, `backend/app/main.py:208-224`.

## Deployment validation

**Preconditions:** Authorized host, `.env` created from AWS example, strong secrets supplied through secure process, readable root-owned/controlled YouTube cookie source where used, backup directory, Docker Compose, Nginx, and installed systemd templates.

**Steps:** `docker compose -f docker-compose.aws.yml config --quiet`; `bash -n scripts/*.sh`; `scripts/deploy-aws.sh --dry-run`; Nginx `nginx -t`; verify loopback-only app port; real deploy only after backup; check container health, `/readiness`, logs, timers, backup verification, direct SPA routes, and HTTPS headers.

**Expected result:** Preflight fails safely for missing secrets/cookie; deploy creates verified backup and commit-tagged image; unhealthy replacement rolls back; Nginx is the only public listener.

**Relevant files/tests:** deployment/Compose/Nginx/systemd files; `test_backup_restore.py`, `test_health.py`, production Playwright.

The exact live domain, DuckDNS record, certificate status, firewall, and installed service state are **Not verified from the current codebase.** Test them on the authorized host.
