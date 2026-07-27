# 01 — Page-by-page guide

## Route and navigation rules

The frontend does not use React Router. `App` reads `window.location.pathname`, matches exact strings or three ID patterns, and lazy-loads a page (`frontend/src/App.tsx:110-164`). Links are normal `<a>` elements, so navigation reloads the page. In production, FastAPI returns `index.html` for safe, unknown non-API paths, which makes direct route refreshes work (`backend/app/main.py:208-224`).

Public pages are `/`, `/landing`, `/login`, `/privacy`, `/terms`, and `/security`. Every other matched page and the protected not-found page is wrapped in `Authenticated`; it checks `/api/v1/auth/session` and redirects to `/login?next=...` if access is denied (`frontend/src/App.tsx:64-107`). There is no separate admin-only frontend route.

The primary sidebar is defined at `frontend/src/components/AppShell.tsx:30-41,153-178,219-247`:

| Item | Destination | Availability and status |
|---|---|---|
| Product Showcase | `/` | Always listed inside the authenticated shell, though `/` itself is public. Fully implemented static landing page. |
| Overview | `/dashboard` | Authenticated. Fully implemented dashboard, but its “Retrieval health” bars are fixed display values, not measurements. |
| Knowledge | `/knowledge-bases` | Authenticated. Create/list/open works; knowledge-base deletion is not present. |
| Add knowledge | `/upload` | Authenticated shortcut above the nav. Requires a knowledge base before intake. |
| Source library | `/upload` | Authenticated. Documents and media are combined in one library. |
| Research chat | `/chat` | Authenticated. Requires a knowledge base with ready indexed sources. |
| Video intelligence | `/video` | Authenticated. Requires an ingested media source. |
| Compare & reports | `/intelligence` | Authenticated. Requires ready documents; comparison needs at least two. |
| Evaluation | `/evaluation` | Authenticated. Running works only after a dataset and cases exist; the UI cannot create them. |
| Feedback | `/feedback` | Authenticated. Analytics display only; no visible feedback submission or conversion control. |
| Templates | `/templates` | Authenticated. Templates are fixed server data; Run Workflow opens chat with a prompt. |
| Settings | `/settings` | Authenticated footer item. Read-only configuration plus model warmup. |
| Sign out | `/` after `POST /auth/logout` | Always in authenticated shell; clears the local bearer token even when logout fails. |

The sidebar workspace switcher at `frontend/src/components/AppShell.tsx:144-151` is a display-only button with no click handler. The two “Recent” links are fixed labels, not a query of recent activity (`:180-190`). The command palette opens with Ctrl/Cmd+K or `/`, sends entered text to `/chat?question=...`, and provides upload/chat/video shortcuts (`:83-108,277-305`). Theme and sidebar/mobile controls work locally; the theme is stored in `localStorage` (`:43-59`).

## 1. Landing page

**Page:** Product Showcase / Landing

**Route:** `/` and `/landing`

**Purpose:** Explain the product, demo workflow, privacy warning, and limitations before sign-in.

**Main features:** Public header; “Try the demo,” GitHub, and README links; product capability cards; a three-step workflow; visible limitations; privacy, terms, and security links. It is informational and does not load API data (`frontend/src/pages/LandingPage.tsx:17-136`).

**How to use it:** Read the overview and limitations. Select **Try the demo** to open `/login`. Use the footer for public legal pages.

**How to test it:** Open `/` while signed out. Confirm all sections render, anchor links scroll, `/login` opens, external GitHub links use a new tab, and legal links work. Refresh `/landing` directly in a production build.

**Expected result:** A public marketing page appears without an authentication request blocking it.

**Possible errors:** A wrong repository URL can only be fixed in code. If direct `/landing` refresh returns 404, the production SPA fallback is missing or the proxy is not passing the route to FastAPI.

**Frontend files:** `frontend/src/pages/LandingPage.tsx`; route selection in `frontend/src/App.tsx:118-120`; styles in `frontend/src/styles/index.css`.

**API endpoints:** None.

**Backend files:** Production fallback in `backend/app/main.py:208-224`.

**Database models/tables:** None.

**Tests:** Browser coverage in `frontend/e2e/enterprise-rag.spec.ts` and `frontend/e2e/production-smoke.spec.ts`; no dedicated unit test.

## 2. Login page

**Page:** Sign in / Create account

**Route:** `/login`

**Purpose:** Enter open, shared demo-password, or account access mode.

**Main features:** Reads access configuration and current session; open mode shows a continue link; demo-password mode shows one password field; accounts mode supports registration and email/password sign-in. A safe `next` path returns the user to the requested local page (`frontend/src/pages/LoginPage.tsx:12-76`). Successful account login stores a bearer token; the backend also sets a signed session cookie.

**How to use it:** In open mode select **Continue to workspace**. In demo-password mode enter the operator-provided demo password. In accounts mode choose sign in or register, complete the form, and submit.

**How to test it:** Test each configured mode separately. Visit `/dashboard` signed out and confirm redirect to `/login?next=%2Fdashboard`. Submit a wrong password and confirm a message and re-enabled button. Submit valid credentials and confirm navigation to the safe next path. Try `?next=https://example.com` and confirm it does not redirect off-site.

**Expected result:** The session becomes authenticated and a protected route opens. Account mode also stores the returned token in `localStorage`.

**Possible errors:** Access service unavailable; invalid credentials; shared-login lockout after repeated failures; duplicate account email; invalid production secret/hash settings preventing startup. Loading is cleared after success or error (`frontend/src/pages/LoginPage.tsx:50-75`).

**Frontend files:** `frontend/src/pages/LoginPage.tsx`; auth guard in `frontend/src/App.tsx:64-107`; API functions in `frontend/src/api/client.ts:574-626`.

**API endpoints:** `GET /api/v1/auth/config`; `GET /api/v1/auth/session`; `POST /api/v1/auth/demo/login`; `POST /api/v1/auth/register`; `POST /api/v1/auth/login`; `POST /api/v1/auth/logout`.

**Backend files:** `backend/app/api/routes/auth.py:93-248`; `backend/app/core/security.py`; `backend/app/core/middleware.py`.

**Database models/tables:** `users` for accounts mode (`backend/app/models/user.py:26-42`). Shared demo sessions are signed tokens, not session rows.

**Tests:** `frontend/src/pages/LoginPage.test.tsx`; `backend/tests/test_public_demo_auth.py`; auth paths also appear in both Playwright specs.

## 3. Legal pages

**Page:** Privacy, Terms / Demo Notice, and Security

**Route:** `/privacy`, `/terms`, `/security`

**Purpose:** Tell public-demo users what is stored, what they must not upload, demo limits, and how security is approached.

**Main features:** One `LegalPage` selects a static content object by route. It includes back navigation, repository/issue links, and links between the three notices (`frontend/src/pages/LegalPage.tsx:1-101`).

**How to use it:** Open the page from the landing footer and read the notice before uploading data.

**How to test it:** Open and refresh all three URLs while signed out. Confirm the title and sections change, links work, and no protected-route redirect occurs.

**Expected result:** Static public content is visible.

**Possible errors:** These notices are project text, not proof of legal compliance. A deployment with different retention or controls can make the text inaccurate. Formal legal review is **Not verified from the current codebase.**

**Frontend files:** `frontend/src/pages/LegalPage.tsx`; `frontend/src/App.tsx:124-126`.

**API endpoints:** None.

**Backend files:** Public-route allow-list in `backend/app/core/middleware.py`; SPA fallback in `backend/app/main.py:208-224`.

**Database models/tables:** None directly.

**Tests:** Public route checks in `frontend/e2e/production-smoke.spec.ts`; no dedicated component test.

## 4. Overview dashboard

**Page:** Overview

**Route:** `/dashboard` and alias `/workspace`

**Purpose:** Summarize knowledge bases, sources, model configuration, and shortcuts.

**Main features:** Loads knowledge bases and RAG configuration, then documents and media for every knowledge base. Shows source/readiness totals, current engine/model/device, recent sources, model information, storage mode, quick actions, and five “Retrieval health” bars (`frontend/src/pages/DashboardPage.tsx:31-314`). The bar values `92, 76, 86, 97, 82` are hard-coded (`:243-248`); they are presentation, not live metrics. The grade changes only based on whether any source is ready.

**How to use it:** Review totals and recent sources. Open a document/media record or use quick actions for upload, chat, video, or intelligence.

**How to test it:** Start with an empty database and confirm the empty/zero state. Create two knowledge bases, one document, and one media source; refresh and compare counts. Simulate one child list failure and confirm the page reports partial source failure instead of spinning forever.

**Expected result:** The dashboard reflects stored collections and source status. Model data matches `/api/v1/rag/config`.

**Possible errors:** A failed knowledge-base or configuration request shows a page error. A failed per-knowledge-base source request produces a partial-data warning. Health bars must not be interpreted as measured accuracy.

**Frontend files:** `frontend/src/pages/DashboardPage.tsx`; `frontend/src/App.tsx:127-128`.

**API endpoints:** `GET /api/v1/knowledge-bases`; `GET /api/v1/knowledge-bases/{id}/documents`; `GET /api/v1/knowledge-bases/{id}/media`; `GET /api/v1/rag/config`.

**Backend files:** `backend/app/api/routes/knowledge_bases.py`; `documents.py:121-130`; `media.py:192-206`; `rag.py:148-230`.

**Database models/tables:** `knowledge_bases`, `documents`, `media_sources`.

**Tests:** Main path covered by Playwright specs; no dedicated dashboard unit test.

## 5. Knowledge bases page

**Page:** Knowledge

**Route:** `/knowledge-bases`

**Purpose:** Create and list top-level source collections.

**Main features:** Name/description form, loading/error states, collection cards, source count, lifecycle metadata, and **Open workspace** links (`frontend/src/pages/KnowledgeBasesPage.tsx:7-126`). There is no edit or delete control.

**How to use it:** Enter a name and optional description, submit, then select **Open workspace** or go to Add knowledge.

**How to test it:** Create a valid collection and confirm it appears first. Submit an empty name and confirm browser/form validation. Reach the configured knowledge-base quota and confirm the backend returns an actionable limit error. Refresh and confirm persistence.

**Expected result:** A `knowledge_bases` row is created with lifecycle timestamps and appears in the list.

**Possible errors:** Duplicate names are allowed because the model has an index, not a unique constraint. Quota errors can tell the user to remove a collection even though there is no delete route/UI; use cleanup or an operator procedure instead.

**Frontend files:** `frontend/src/pages/KnowledgeBasesPage.tsx`; API calls at `frontend/src/api/client.ts:149-162`.

**API endpoints:** `GET /api/v1/knowledge-bases`; `POST /api/v1/knowledge-bases`; workspace uses `GET /api/v1/knowledge-bases/{id}` only in backend/API, not on the workspace page.

**Backend files:** `backend/app/api/routes/knowledge_bases.py:18-76`; `backend/app/repositories/knowledge_bases.py`.

**Database models/tables:** `knowledge_bases` (`backend/app/models/knowledge_base.py:14-30`) and its child relationships.

**Tests:** `backend/tests/test_knowledge_bases.py`; Playwright creation/navigation coverage. No dedicated frontend unit test.

## 6. Knowledge-base workspace

**Page:** Focused collection workspace

**Route:** `/knowledge-bases/:id`

**Purpose:** Provide shortcuts intended to carry a knowledge-base ID into other tools.

**Main features:** Static heading, overview/source/chat/summary/compare/report/evaluation/settings tabs, and a displayed collection ID (`frontend/src/pages/WorkspacePage.tsx:12-50`). It does not fetch the collection, display its real name, or validate that it exists. It appends `knowledgeBase=<id>` to destinations.

**How to use it:** Select a shortcut. Source library and chat read the query parameter. Other destinations may not honor it.

**How to test it:** Open a real ID and a fake ID. Confirm both render the same static page. Test each link and inspect whether the destination keeps and uses `knowledgeBase`. Confirm that the Evaluation shortcut currently opens `/intelligence`, not `/evaluation`.

**Expected result:** Navigation occurs with the ID in the query string.

**Possible errors:** This page is partial. `IntelligencePage` selects the first knowledge base instead of reading the query parameter, Settings ignores it, and several tabs share `/intelligence`. The “Evaluation” target is incorrect for the named feature (`frontend/src/pages/WorkspacePage.tsx:14-20`).

**Frontend files:** `frontend/src/pages/WorkspacePage.tsx`; dynamic match at `frontend/src/App.tsx:114,151-152`.

**API endpoints:** None called by this page.

**Backend files:** None directly.

**Database models/tables:** None read by this page, though the ID represents `knowledge_bases.id`.

**Tests:** No targeted unit or backend test; basic route behavior is covered only indirectly by browser tests.

## 7. Source library and intake

**Page:** Source library / Add knowledge

**Route:** `/upload` and alias `/documents`

**Purpose:** Add, process, browse, search, sort, refresh, and retry document/media sources.

**Main features:** Knowledge-base selector; file and public-URL modes; drag/drop; document/media language choices; progress messages; sequential processing; bounded polling; combined source library; text search; status filter; name/recent sort; refresh; source detail links; failed-source retry (`frontend/src/pages/UploadPage.tsx:63-600`). Supported frontend extensions are PDF/TXT/DOCX, MP4/MOV/MKV/WEBM, and M4A/MP3/WAV. Backend validation remains authoritative.

**How to use it:** Create/select a knowledge base. For files, select supported sources and start intake. For URL mode, paste an allowed public media URL. Wait for completion or use refresh later. Open a source card for details.

**How to test it:** Upload a valid TXT, PDF, DOCX, MP3, and MP4 separately. Confirm each reaches ready or reports a terminal reason. Test wrong extension, wrong magic bytes, duplicate content, oversized file, page/duration limit, and quota. Test a public URL, a private/loopback URL, and a YouTube URL in an environment with and without valid cookies/Deno. Confirm polling stops after about 180 seconds for a document and 480 seconds for intake media, and the page clears `uploading` in `finally` (`:190-220,227-245`).

**Expected result:** Direct sources are stored, processed, and shown as ready; a media transcript also becomes a document source for retrieval.

**Possible errors:** No knowledge base; unsupported/corrupt file; duplicate checksum; size/page/duration/quota limit; request timeout; model unavailable; transcription failure; blocked/unsafe URL; expired cookies; YouTube JavaScript/PO-token/no-format restrictions; AWS/cloud IP rejection. URL/YouTube import is best-effort; direct media upload is the documented fallback.

**Frontend files:** `frontend/src/pages/UploadPage.tsx`; `frontend/src/api/client.ts:164-220,356-393,425-435`.

**API endpoints:** Document list/upload/process/retry/status; media list/upload/from-url/retry/detail. See the API guide for exact URLs.

**Backend files:** `backend/app/api/routes/documents.py`; `media.py`; `backend/app/services/documents.py`; `processing.py`; `media.py`; `backend/app/document_processing/`; `backend/app/media/`.

**Database models/tables:** `knowledge_bases`, `documents`, `document_sections`, `document_chunks`, `media_sources`, `transcript_jobs`, `transcript_segments`, `media_summaries`, `media_chapters`, `media_processing_attempts`.

**Tests:** `backend/tests/test_documents.py`, `test_processing.py`, `test_media.py`, `test_policy_e2e.py`; Playwright specs. Real transcription is separately marked.

## 8. Document detail

**Page:** Document source detail

**Route:** `/documents/:id`

**Purpose:** Inspect and manage one uploaded document and its extracted/indexed content.

**Main features:** Parallel detail/extraction/preview/chunk load; status and processing timeline; start/retry/delete; original-file link; page, character, chunk, and index counts; warnings/errors; plain-text preview; paginated chunks; optional highlighted chunk from `?chunk=` (`frontend/src/pages/DocumentPage.tsx:35-338`). Processing polling is capped at 180 checks, one per second (`:74-106`). Text is rendered as React text inside `<pre>`, not injected HTML.

**How to use it:** Open a document from the source library. Start processing if only uploaded, retry if failed, inspect extracted text/chunks, open the original, or delete the record and file.

**How to test it:** Test uploaded, processing, ready, failed, and missing IDs. Open a citation-linked chunk query and confirm scrolling. Paginate chunks. Delete and confirm return to the same knowledge-base library. Simulate a stuck process and verify the bounded timeout message.

**Expected result:** Ready documents show extracted sections, preview, and indexed chunks. Delete returns 204 and removes the source.

**Possible errors:** Extraction endpoint can fail before extraction exists; corrupt files, missing OCR binaries, page limits, embedding/model problems, or background task failure can make processing terminal. A request/polling timeout does not prove server work stopped.

**Frontend files:** `frontend/src/pages/DocumentPage.tsx`; dynamic route in `frontend/src/App.tsx:112,147-148`; `ProcessingTimeline` and `StatusBadge` components.

**API endpoints:** `GET /documents/{id}`; `/content`; `/processing`; `/extraction`; `/preview`; `/chunks`; `POST /process`; `POST /retry`; `DELETE /documents/{id}`.

**Backend files:** `backend/app/api/routes/documents.py:103-334`; `backend/app/services/processing.py`; extraction/chunking/OCR/table files under `backend/app/document_processing/`.

**Database models/tables:** `documents`, `document_sections`, `document_chunks`.

**Tests:** `frontend/src/pages/DocumentPage.test.tsx`; `frontend/src/components/StatusBadge.test.tsx`; `backend/tests/test_documents.py`; `test_processing.py`.

## 9. Research chat

**Page:** Research chat

**Route:** `/chat`

**Purpose:** Ask grounded questions about a knowledge base and inspect evidence.

**Main features:** Knowledge-base selection; new/open/delete sessions; query prefill from `?question=`; concise/detailed response modes; auto/Arabic/English output; explain/debug toggle; suggestions; elapsed time; confidence; verification badges; citations; evidence drawer with retrieval details (`frontend/src/pages/ChatPage.tsx:84-535`). Requests have a 210-second client timeout (`frontend/src/api/client.ts:37-38,222-245`).

**How to use it:** Select a knowledge base with ready sources, enter a question, choose answer/language options, and submit. Select citations to inspect source locations. Reopen earlier sessions from the session list.

**How to test it:** Ask one answerable and one unsupported question. Confirm the supported answer has citations and the unsupported answer says evidence is insufficient. Test Arabic and English, debug mode, session reopening/deletion, and a prefilled template/command query. Simulate a backend timeout and confirm the composer stops loading and shows an actionable error.

**Expected result:** The answer is stored as chat messages with source citations, verification status, model metadata, and timing. Retrieval evidence appears in the UI.

**Possible errors:** No knowledge base or ready chunks; model cold/load failure; queue busy; generation/retrieval timeout; weak evidence; authentication expiry. The CircleStop icon shown while asking has no cancel handler. “Regenerate” only fills the question with “Answer again more concisely.”; the user must submit again (`frontend/src/pages/ChatPage.tsx:393-419`).

**Frontend files:** `frontend/src/pages/ChatPage.tsx`; `CitationList.tsx`; `VerificationBadge.tsx`; API calls at `frontend/src/api/client.ts:222-263`.

**API endpoints:** `POST /knowledge-bases/{id}/ask`; `POST/GET /chat-sessions`; `GET/DELETE /chat-sessions/{id}`; `GET /rag/config`; debug API `POST /knowledge-bases/{id}/retrieve` is not directly called by the page.

**Backend files:** `backend/app/api/routes/rag.py`; `backend/app/services/rag.py`; `retrieval.py`; `reranking.py`; `query_rewriting.py`; `answer_processing.py`; `verification.py`.

**Database models/tables:** `chat_sessions`, `chat_messages`, `document_chunks`, `documents`, `knowledge_bases`.

**Tests:** `frontend/src/pages/ChatPage.test.tsx`; `CitationList.test.tsx`; `backend/tests/test_rag.py`, `test_multilingual.py`, `test_policy_e2e.py`; optional real-model tests.

## 10. Video intelligence

**Page:** Video intelligence / Media detail

**Route:** `/video`, alias `/media`, and `/media/:id`

**Purpose:** Browse processed audio/video, read/search synchronized transcripts, inspect derived intelligence, ask questions, and export results.

**Main features:** Knowledge-base/media selectors; direct-route lookup; bounded status polling (120 attempts at 1.5 seconds); native audio/video player for uploads; original URL link; synchronized transcript seek/highlight; server-side transcript search; paged transcript load; summaries, key points, chapters, actions, decisions, entities, quiz/glossary and other deterministic outputs; media Q&A; transcript TXT/Markdown/JSON and summary Markdown exports (`frontend/src/pages/VideoPage.tsx:58-514`).

**How to use it:** Ingest media first, select it, wait until ready, search or click transcript segments to seek, review intelligence tabs, ask a source question, or download an export.

**How to test it:** Use a short direct MP3 and MP4. Confirm player content, segment seeking, search, load more, all intelligence sections, Q&A citations/timestamps, and four export links. Open `/media/<id>?t=10` and verify initial seek. Test failed and long-running sources. Test a public URL only where network/cookie policy permits.

**Expected result:** A ready source has timestamped transcript segments, deterministic intelligence, a transcript-backed document index, grounded media answers, and downloadable exports.

**Possible errors:** ffprobe/ffmpeg missing; duration/type failure; subtitle parsing problem; faster-whisper model unavailable; YouTube/cloud restriction; no audio format; cookies expired; processing timeout. There is a backend delete route, but the frontend has no delete-media client/control.

**Frontend files:** `frontend/src/pages/VideoPage.tsx`; route matches at `frontend/src/App.tsx:113,143-150`; API functions at `frontend/src/api/client.ts:356-466`.

**API endpoints:** Media list/detail/content/transcript/search/intelligence/ask/export/retry. `DELETE /media/{id}` exists but is not used by this page.

**Backend files:** `backend/app/api/routes/media.py`; `backend/app/services/media.py`; `backend/app/media/transcription.py`; `backend/app/media/intelligence.py`.

**Database models/tables:** `media_sources`, `transcript_jobs`, `transcript_segments`, `media_summaries`, `media_chapters`, `media_processing_attempts`, `media_export_records`, plus transcript-backed `documents` and `document_chunks`.

**Tests:** `backend/tests/test_media.py`, `test_policy_e2e.py`; `backend/tests/test_real_transcription.py` only when opted in; Playwright smoke paths. No dedicated VideoPage unit test.

## 11. Compare and reports

**Page:** Intelligence

**Route:** `/intelligence`

**Purpose:** Generate grounded summaries, document comparisons, and research reports.

**Main features:** Mode tabs; knowledge-base and ready-document selection; short/detailed/section summaries; comparison of at least two documents; report title/objective; auto/Arabic/English output; elapsed time; source citations and verification; Markdown report download (`frontend/src/pages/IntelligencePage.tsx:26-445`).

**How to use it:** Select a knowledge base, choose ready documents, choose a mode, fill mode-specific fields, set language, and generate. Download report Markdown if needed.

**How to test it:** Process two small documents. Test every summary kind, comparison, and report. Confirm required selection messages, citations, partial-result warning, timeout/model-busy messages, and Markdown download. Open `?knowledgeBase=<second-id>` and note that current code still selects the first returned collection.

**Expected result:** The backend returns a grounded structured result with citations, verification, language, model, and generation metadata.

**Possible errors:** No ready documents; too few comparison sources; invalid section; model unavailable/busy; retrieval/generation timeout; context too large; partial multi-section report. Generated document intelligence is returned to the browser and is not persisted in a dedicated table.

**Frontend files:** `frontend/src/pages/IntelligencePage.tsx`; `frontend/src/api/client.ts:265-330`.

**API endpoints:** `POST /api/v1/intelligence/summaries`; `/comparisons`; `/reports`; document and knowledge-base list endpoints.

**Backend files:** `backend/app/api/routes/intelligence.py`; `backend/app/services/intelligence.py:40-443`; language and verification services.

**Database models/tables:** Reads `knowledge_bases`, `documents`, `document_sections`, and `document_chunks`; no result persistence table.

**Tests:** `backend/tests/test_intelligence.py`, `test_multilingual.py`, `test_low_memory.py`; Playwright navigation. No dedicated component unit test.

## 12. Evaluation page

**Page:** Evaluation

**Route:** `/evaluation`

**Purpose:** Run and compare repeatable RAG benchmark datasets.

**Main features:** Dataset selector; latest metrics; execute-run button; run history; pass/fail/correctness/faithfulness/citation/latency values; client-generated Markdown export (`frontend/src/pages/EvaluationPage.tsx:28-183`).

**How to use it:** First create a dataset and cases through the API or demo seed because the page has no creation form. Select a dataset, run it, then review/export metrics.

**How to test it:** Create one supported case and one unsupported case through the API. Open the page, run the dataset, confirm totals and stored history, and inspect the export. Test an empty dataset and a model failure.

**Expected result:** Each case calls the normal RAG service and stores a result. The run aggregates correctness, faithfulness, citation accuracy, median latency, and p95 latency (`backend/app/services/evaluation.py:90-209`).

**Possible errors:** No dataset/cases; 25-case public-demo limit; generation errors; evaluation timeout. Correctness uses token coverage (50% threshold) plus found/not-found/citation rules, not human or semantic grading (`backend/app/services/evaluation.py:26-31,131-159`).

**Frontend files:** `frontend/src/pages/EvaluationPage.tsx`; API functions `frontend/src/api/client.ts:528-572`.

**API endpoints:** `GET/POST /evaluation/datasets`; `POST /evaluation/cases`; `GET/POST /evaluation/runs`. The UI only uses the GET lists and POST run.

**Backend files:** `backend/app/api/routes/evaluation.py`; `backend/app/services/evaluation.py`.

**Database models/tables:** `evaluation_datasets`, `evaluation_cases`, `evaluation_runs`, `evaluation_results`.

**Tests:** `backend/tests/test_evaluation.py`; Playwright route coverage. No dedicated component test.

## 13. Feedback page

**Page:** Feedback analytics

**Route:** `/feedback`

**Purpose:** Show stored helpful/unhelpful totals and complaint categories.

**Main features:** Loads analytics and evaluation datasets; displays total feedback, helpful count/rate, unhelpful count, and category bars (`frontend/src/pages/FeedbackPage.tsx:13-107`). `convertFeedbackToEval` and datasets are imported/loaded but there is no feedback list, selector, submit form, or conversion button.

**How to use it:** Feedback must first be submitted through the API. Then open the page to view aggregate analytics.

**How to test it:** Submit helpful and unhelpful records with different categories using curl. Refresh and compare totals and bars. Confirm an API error produces a terminal message.

**Expected result:** Counts are calculated from `user_feedback`; category counts include unhelpful records only (`backend/app/services/feedback.py:57-83`).

**Possible errors:** Empty state is expected when no API-created feedback exists. The product chat has no visible rating buttons, so normal users cannot populate this from the UI. Conversion to an evaluation case is backend/client capability only.

**Frontend files:** `frontend/src/pages/FeedbackPage.tsx`; unused submission/conversion client functions at `frontend/src/api/client.ts:486-526`.

**API endpoints:** `POST /feedback`; `GET /feedback/analytics`; `POST /feedback/{id}/convert-to-eval`.

**Backend files:** `backend/app/api/routes/feedback.py`; `backend/app/services/feedback.py`.

**Database models/tables:** `user_feedback`, `evaluation_datasets`, `evaluation_cases`.

**Tests:** `backend/tests/test_evaluation.py` covers evaluation interaction; feedback backend behavior may be exercised there. No dedicated frontend feedback test or complete end-to-end UI test.

## 14. Templates page

**Page:** Action templates

**Route:** `/templates`

**Purpose:** Offer reusable prompt starters for common analysis tasks.

**Main features:** Server-loaded fixed template cards; category filters; source type/output/safety metadata; **Run Workflow** link that opens `/chat?question=<prompt>` (`frontend/src/pages/TemplatesPage.tsx:31-101`). The 13 templates are hard-coded in `backend/app/services/templates.py:21-192`, not user-created or database-backed.

**How to use it:** Filter by category, select a template, then choose **Run Workflow**. On chat, choose a ready knowledge base and submit or edit the prefilled instruction.

**How to test it:** Confirm all categories and cards load, filters change the visible cards, and a workflow prompt is URL-encoded and appears in chat. Test API failure.

**Expected result:** The selected instruction is prefilled in the chat composer; it is not executed automatically.

**Possible errors:** A template can claim a structured output type, but the page routes every template to ordinary chat; it does not enforce that output schema. Templates are code constants and cannot be edited in the UI.

**Frontend files:** `frontend/src/pages/TemplatesPage.tsx`; list client at `frontend/src/api/client.ts:472-484`.

**API endpoints:** `GET /api/v1/templates`; `GET /api/v1/templates/{template_id}` (detail is not used by the page).

**Backend files:** `backend/app/api/routes/templates.py`; `backend/app/services/templates.py`.

**Database models/tables:** None.

**Tests:** API route behavior may be exercised through broader policy/browser tests; no dedicated templates unit-test file.

## 15. Settings page

**Page:** Model and runtime settings

**Route:** `/settings`

**Purpose:** Show effective RAG/model/runtime settings and request model warmup.

**Main features:** Read-only rows for engine, model names/status, device, quantization, vector store, retrieval/chunk/generation limits, upload/demo limits, and queue state; refresh; **Warm models** action; restart/reindex explanation (`frontend/src/pages/SettingsPage.tsx:6-118`). There are no editable settings fields.

**How to use it:** Review effective values. Select **Warm models** to load the configured embedding/generation models, then refresh status.

**How to test it:** Compare every shown value with `/api/v1/rag/config`. Test warmup when cold, loading, ready, and failed. Simulate backend unavailability and confirm the terminal error and available retry; the unit test covers this.

**Expected result:** Configuration loads, warmup returns `202`, and later status becomes ready if model files/resources are available.

**Possible errors:** No network/cache for model download; memory exhaustion; incompatible quantization/device; queue full; load timeout. Settings changes require environment/config editing and process restart. Changing the embedding model requires reprocessing/reindexing affected sources.

**Frontend files:** `frontend/src/pages/SettingsPage.tsx`; `frontend/src/api/client.ts:337-343`.

**API endpoints:** `GET /api/v1/rag/config`; `POST /api/v1/rag/warmup`.

**Backend files:** `backend/app/api/routes/rag.py:148-273`; `backend/app/ai/warmup.py`; providers/configuration files.

**Database models/tables:** No settings table. Warm/model state is in application memory; cache files are on disk.

**Tests:** `frontend/src/pages/SettingsPage.test.tsx`; `backend/tests/test_ai_providers.py`, `test_hardware.py`, `test_low_memory.py`.

## Protected not-found state

Any unmatched path renders a “Page not found” card inside the authenticated shell (`frontend/src/App.tsx:153-164`). It is not a separate route or page component. Signed-out users are redirected to login before seeing it. Test an unknown path both signed out and signed in, then use **Return to dashboard**. In production, FastAPI must return the SPA rather than its own 404 for this to work.
