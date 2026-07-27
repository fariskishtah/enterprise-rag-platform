# 04 — API reference

The configured default prefix is `/api/v1` (`backend/app/core/config.py:32`). The 60 operations below are included by `backend/app/api/router.py:17-28`. FastAPI also generates interactive OpenAPI documentation at `/docs` unless a deployment disables it externally.

In the tables, handler basenames such as `rag.py` mean the exact path `backend/app/api/routes/rag.py`; the same rule applies to every named route file. Named service classes are mapped to their exact files in [the feature guide](02-feature-guide.md) and [file map](03-file-map.md).

## Safe curl setup

```bash
BASE=http://127.0.0.1:7860/api/v1
COOKIE=/tmp/enterprise-rag-guide-cookie.txt

# Only for a demo_password instance. This value is deliberately fake.
curl -sS -c "$COOKIE" -H 'Content-Type: application/json' \
  -d '{"password":"example-demo-password"}' "$BASE/auth/demo/login"
```

Protected examples use `-b "$COOKIE"`. In `open` mode the cookie is not needed. In `accounts` mode, use the returned `access_token` as `-H "Authorization: Bearer $TOKEN"`. Replace placeholder IDs and local sample paths. Do not place a real password or token in shell history.

Error responses use a stable JSON envelope from `backend/app/core/errors.py`; validation errors are normally 422. Authentication middleware protects all API paths except the explicitly public auth/health/readiness paths (`backend/app/core/middleware.py`).

## Health and operations (4)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `GET /health` | Lightweight liveness. Public. | None. | `200 {"status":"ok"}`. | `health.py:19-21`; no service; Docker/probes. | `curl -i "$BASE/health"` |
| `GET /readiness` | DB, schema, and writable-path readiness. Public. | None. | `200` ready checks or `503` failed checks. | `health.py:59-99`; engine/filesystem; operator only. | `curl -i "$BASE/readiness"` |
| `GET /ready` | Backward-compatible readiness alias. Public. | None. | Same as readiness. | `health.py:102-104`; same checks; operator only. | `curl -i "$BASE/ready"` |
| `GET /operations/status` | Safe uptime/build/profile/model/queue/storage/maintenance summary. Protected. | None. | `200` object without secrets. | `health.py:116-170`; operation markers/app state; no page. | `curl -sS -b "$COOKIE" "$BASE/operations/status"` |

## Authentication (7)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `GET /auth/config` | Tell login page which access mode is active. Public. | None. | `AccessConfiguration {mode, session_expiry_minutes}`. | `auth.py:93-100`; settings; Login. | `curl -sS "$BASE/auth/config"` |
| `GET /auth/session` | Report whether the current request is authenticated. Public. | Optional cookie/bearer. | `SessionRead {mode, authenticated, expires_at, role}`. | `auth.py:103-114`; claim reader; auth guard/Login. | `curl -sS -b "$COOKIE" "$BASE/auth/session"` |
| `POST /auth/demo/login` | Shared-password login. Public but rate-limited. | JSON `{password}`. | `SessionRead` plus signed cookie. | `auth.py:117-148`; bcrypt/claims/login limiter; Login. | `curl -i -c "$COOKIE" -H 'Content-Type: application/json' -d '{"password":"example-demo-password"}' "$BASE/auth/demo/login"` |
| `POST /auth/logout` | Clear the session cookie. Public. | None. | `204`. | `auth.py:151-162`; cookie clear; AppShell. | `curl -i -b "$COOKIE" -c "$COOKIE" -X POST "$BASE/auth/logout"` |
| `POST /auth/register` | Create an account in accounts mode. Public. | JSON `{email,password,full_name?}`. | `201 UserRead`. | `auth.py:165-200`; SQLAlchemy/bcrypt; Login. | `curl -sS -H 'Content-Type: application/json' -d '{"email":"owner@example.test","password":"safe-example-passphrase","full_name":"Example Owner"}' "$BASE/auth/register"` |
| `POST /auth/login` | Account login. Public. | JSON `{email,password}`. | `TokenResponse` plus signed cookie. | `auth.py:203-238`; user lookup/claims; Login. | `curl -sS -c "$COOKIE" -H 'Content-Type: application/json' -d '{"email":"owner@example.test","password":"safe-example-passphrase"}' "$BASE/auth/login"` |
| `GET /auth/me` | Return identity derived from current claims. Protected. | None. | `UserRead`. | `auth.py:241-248`; request principal; no current page. | `curl -sS -b "$COOKIE" "$BASE/auth/me"` |

## Knowledge bases (3)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `GET /knowledge-bases` | List collections. Protected. | None. | `KnowledgeBaseList {items,total}`. | `knowledge_bases.py:56-62`; repository; Dashboard/KB/Upload/Chat/Video/Intelligence. | `curl -sS -b "$COOKIE" "$BASE/knowledge-bases"` |
| `POST /knowledge-bases` | Create collection. Protected. | JSON `{name,description?}`. | `201 KnowledgeBaseRead`. | `knowledge_bases.py:32-53`; repository/lifecycle; KB page. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d '{"name":"Guide KB","description":"Safe test collection"}' "$BASE/knowledge-bases"` |
| `GET /knowledge-bases/{knowledge_base_id}` | Get one collection and document count. Protected. | Path `knowledge_base_id`. | `KnowledgeBaseRead`. | `knowledge_bases.py:65-76`; repository; no current page calls it. | `curl -sS -b "$COOKIE" "$BASE/knowledge-bases/$KB_ID"` |

## Documents (11)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `POST /knowledge-bases/{knowledge_base_id}/documents` | Validate/store document. Protected. | Multipart `file`. | `201 DocumentRead`. | `documents.py:103-119`; `DocumentService`; Upload. | `curl -sS -b "$COOKIE" -F 'file=@./sample.txt;type=text/plain' "$BASE/knowledge-bases/$KB_ID/documents"` |
| `GET /knowledge-bases/{knowledge_base_id}/documents` | List collection documents. Protected. | Path ID. | `DocumentList`. | `documents.py:121-130`; `DocumentService`; Dashboard/Upload/Intelligence. | `curl -sS -b "$COOKIE" "$BASE/knowledge-bases/$KB_ID/documents"` |
| `GET /documents/{document_id}` | Get one document. Protected. | Path ID. | `DocumentRead`. | `documents.py:133-141`; service/repository; Document. | `curl -sS -b "$COOKIE" "$BASE/documents/$DOC_ID"` |
| `GET /documents/{document_id}/content` | Download/open original. Protected. | Path ID. | File response with stored media type. | `documents.py:144-161`; storage; Document/citations. | `curl -fSs -b "$COOKIE" -o /tmp/guide-original "$BASE/documents/$DOC_ID/content"` |
| `POST /documents/{document_id}/process` | Queue first processing attempt. Protected/rate/concurrency. | Path ID. | `202 DocumentRead`. | `documents.py:196-213`; background `DocumentProcessingService`; Upload/Document. | `curl -sS -b "$COOKIE" -X POST "$BASE/documents/$DOC_ID/process"` |
| `POST /documents/{document_id}/retry` | Queue failed processing again. Protected/rate/concurrency. | Path ID. | `202 DocumentRead`. | `documents.py:216-233`; processing service; Upload/Document. | `curl -sS -b "$COOKIE" -X POST "$BASE/documents/$DOC_ID/retry"` |
| `GET /documents/{document_id}/processing` | Poll lifecycle status. Protected. | Path ID. | `DocumentRead`. | `documents.py:236-244`; document service; Upload/Document. | `curl -sS -b "$COOKIE" "$BASE/documents/$DOC_ID/processing"` |
| `GET /documents/{document_id}/extraction` | Read extraction metadata/sections. Protected. | Path ID. | `DocumentExtractionRead`. | `documents.py:247-274`; document service; Document. | `curl -sS -b "$COOKIE" "$BASE/documents/$DOC_ID/extraction"` |
| `GET /documents/{document_id}/preview` | Read bounded extracted text. Protected. | Query `offset>=0`, `limit=1..50000`. | `DocumentPreviewRead`. | `documents.py:277-296`; document service; Document. | `curl -sS -b "$COOKIE" "$BASE/documents/$DOC_ID/preview?offset=0&limit=1000"` |
| `GET /documents/{document_id}/chunks` | Page indexed chunks. Protected. | Query `page>=1`, `page_size=1..100`. | `DocumentChunkList`. | `documents.py:299-316`; document service; Document. | `curl -sS -b "$COOKIE" "$BASE/documents/$DOC_ID/chunks?page=1&page_size=10"` |
| `DELETE /documents/{document_id}` | Delete record, index entry, and stored source. Protected. | Path ID. | `204`. | `documents.py:319-334`; document service/LangChain pipeline/storage; Document. | `curl -i -b "$COOKIE" -X DELETE "$BASE/documents/$DOC_ID"` |

## RAG, retrieval, model configuration, and conversations (8)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `POST /knowledge-bases/{knowledge_base_id}/ask` | Grounded answer. Protected/generation-limited. | `RagAskRequest`: required `question`; optional `session_id,top_k,similarity_threshold,response_mode,output_language,source_document_ids,debug`. | `RagAnswerRead` with answer, citations, retrieval, verification, model/timing/debug. | `rag.py:50-115`; custom or LangChain RAG service; Chat. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d '{"question":"What is the main policy?","debug":true,"output_language":"en"}' "$BASE/knowledge-bases/$KB_ID/ask"` |
| `POST /knowledge-bases/{knowledge_base_id}/retrieve` | Debug retrieval without generation. Protected. | `{query,top_k?,similarity_threshold?,source_document_ids?}`. | `RetrievalResponse {query,sources,embedding_model,elapsed_ms}`. | `rag.py:118-145`; `RetrievalService`; no page direct. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d '{"query":"remote work policy","top_k":3}' "$BASE/knowledge-bases/$KB_ID/retrieve"` |
| `GET /rag/config` | Effective model/retrieval/limit/queue status. Protected. | None. | `RagConfigurationRead`. | `rag.py:148-230`; settings/providers/warmup/queue; AppShell/Dashboard/Chat/Settings. | `curl -sS -b "$COOKIE" "$BASE/rag/config"` |
| `POST /rag/warmup` | Start lazy model warmup. Protected. | None. | `202 {status}`. | `rag.py:233-273`; warmup controller/queue; Settings. | `curl -sS -b "$COOKIE" -X POST "$BASE/rag/warmup"` |
| `POST /chat-sessions` | Create an empty conversation. Protected. | `{knowledge_base_id,title?}`. | `201 ChatSessionRead`. | `rag.py:275-287`; conversation repository; API client does not expose create directly. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"knowledge_base_id\":\"$KB_ID\",\"title\":\"Guide chat\"}" "$BASE/chat-sessions"` |
| `GET /chat-sessions` | List conversations, optionally by KB. Protected. | Query `knowledge_base_id?`. | `ChatSessionList`. | `rag.py:290-299`; conversation repository; Chat. | `curl -sS -b "$COOKIE" "$BASE/chat-sessions?knowledge_base_id=$KB_ID"` |
| `GET /chat-sessions/{chat_session_id}` | Get session and ordered messages. Protected. | Path ID. | `ChatSessionDetail`. | `rag.py:302-317`; conversation repository; Chat. | `curl -sS -b "$COOKIE" "$BASE/chat-sessions/$CHAT_ID"` |
| `DELETE /chat-sessions/{chat_session_id}` | Delete session/messages. Protected. | Path ID. | `204`. | `rag.py:320-330`; conversation repository; Chat. | `curl -i -b "$COOKIE" -X DELETE "$BASE/chat-sessions/$CHAT_ID"` |

## Document intelligence (3)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `POST /intelligence/summaries` | Grounded short/detailed/section summary. Protected/generation-limited. | `{knowledge_base_id,document_ids?,kind,section_index?,output_language?}`. | `SummaryRead`. | `intelligence.py:36-59,117-127`; `SummaryService`; Intelligence. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"knowledge_base_id\":\"$KB_ID\",\"document_ids\":[\"$DOC_ID\"],\"kind\":\"short\",\"output_language\":\"en\"}" "$BASE/intelligence/summaries"` |
| `POST /intelligence/comparisons` | Compare two or more documents. Protected/generation-limited. | `{knowledge_base_id,document_ids[2+],output_language?}`. | `ComparisonRead` sections/citations/verification/partial metadata. | `intelligence.py:62-85,130-140`; `ComparisonService`; Intelligence. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"knowledge_base_id\":\"$KB_ID\",\"document_ids\":[\"$DOC_ID\",\"$DOC2_ID\"]}" "$BASE/intelligence/comparisons"` |
| `POST /intelligence/reports` | Multi-section research report. Protected/generation-limited. | `{knowledge_base_id,document_ids,title,objective,output_language?}`. | `ResearchReportRead` including Markdown and partial metadata. | `intelligence.py:88-113,143-153`; `ReportService`; Intelligence. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"knowledge_base_id\":\"$KB_ID\",\"document_ids\":[\"$DOC_ID\"],\"title\":\"Guide report\",\"objective\":\"Summarize confirmed policy\"}" "$BASE/intelligence/reports"` |

## Media and transcripts (13)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `POST /knowledge-bases/{knowledge_base_id}/media` | Validate/store and optionally process direct media. Protected/upload/transcription-limited. | Multipart `file`; `auto_process=true`; `forced_language=auto|ar|en`; `output_language=auto|ar|en`. | `201 MediaSourceRead`. | `media.py:137-161`; `MediaIngestionService`; Upload. | `curl -sS -b "$COOKIE" -F 'file=@./sample.mp3;type=audio/mpeg' -F auto_process=true -F forced_language=auto -F output_language=en "$BASE/knowledge-bases/$KB_ID/media"` |
| `GET /knowledge-bases/{knowledge_base_id}/media` | List media in collection. Protected. | Path ID. | `MediaSourceList`. | `media.py:192-206`; media repository; Dashboard/Upload/Video. | `curl -sS -b "$COOKIE" "$BASE/knowledge-bases/$KB_ID/media"` |
| `POST /knowledge-bases/{knowledge_base_id}/media/from-url` | Link/process allowed public media URL. Protected/URL/transcription-limited. | `{url,title?,forced_language?,output_language?,auto_process?}`. | `201 MediaSourceRead`. | `media.py:164-189`; ingestion service/URL validation; Upload. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d '{"url":"https://media.example.test/public-sample.mp3","title":"Guide URL","auto_process":false}' "$BASE/knowledge-bases/$KB_ID/media/from-url"` |
| `GET /media/{media_source_id}` | Full media detail/job/attempt/counts. Protected. | Path ID. | `MediaDetailRead`. | `media.py:209-227`; media repository; Upload/Video. | `curl -sS -b "$COOKIE" "$BASE/media/$MEDIA_ID"` |
| `GET /media/{media_source_id}/content` | Stream direct uploaded media. Protected. | Path ID. | File response; 404 for URL-only source. | `media.py:230-247`; storage; Video. | `curl -fSs -b "$COOKIE" -o /tmp/guide-media "$BASE/media/$MEDIA_ID/content"` |
| `POST /media/{media_source_id}/process` | Queue processing. Protected/transcription-limited. | Query `forced_language`, `output_language`. | `202 MediaSourceRead`. | `media.py:284-305`; background `MediaProcessingService`; API client does not expose first process separately. | `curl -sS -b "$COOKIE" -X POST "$BASE/media/$MEDIA_ID/process?forced_language=auto&output_language=en"` |
| `POST /media/{media_source_id}/retry` | Retry a failed source. Protected/transcription-limited. | Same language query. | `202 MediaSourceRead`. | `media.py:308-329`; media processing; Upload. | `curl -sS -b "$COOKIE" -X POST "$BASE/media/$MEDIA_ID/retry?forced_language=auto&output_language=en"` |
| `GET /media/{media_source_id}/transcript` | Page transcript and optional full text. Protected. | `offset>=0`, `limit=1..1000`, `include_full_text`. | `TranscriptRead`. | `media.py:332-354`; media repository; Video. | `curl -sS -b "$COOKIE" "$BASE/media/$MEDIA_ID/transcript?offset=0&limit=50&include_full_text=false"` |
| `GET /media/{media_source_id}/transcript/search` | Search transcript terms. Protected. | Query `query`. | `TranscriptSearchResponse`. | `media.py:357-379`; media repository/search logic; Video. | `curl -sS -b "$COOKIE" --get --data-urlencode 'query=action item' "$BASE/media/$MEDIA_ID/transcript/search"` |
| `GET /media/{media_source_id}/intelligence` | Read derived transcript intelligence. Protected. | Path ID. | `VideoIntelligenceRead`. | `media.py:382-423`; transcript intelligence/stored summaries; Video. | `curl -sS -b "$COOKIE" "$BASE/media/$MEDIA_ID/intelligence"` |
| `POST /media/{media_source_id}/ask` | Ask only against transcript-backed document. Protected/generation-limited. | `RagAskRequest`. | `RagAnswerRead` with timestamp citations. | `media.py:425-463`; `RagService`; Video. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d '{"question":"What decision was made?","output_language":"en"}' "$BASE/media/$MEDIA_ID/ask"` |
| `GET /media/{media_source_id}/export/{export_kind}` | Download rendered transcript/summary. Protected. | Kind: `transcript.txt`, `transcript.md`, `transcript.json`, or `summary.md`. | Text/Markdown/JSON file; records export event. | `media.py:465-521`; media repository/rendering; Video. | `curl -fSs -b "$COOKIE" -o /tmp/transcript.md "$BASE/media/$MEDIA_ID/export/transcript.md"` |
| `DELETE /media/{media_source_id}` | Delete media, descendants, storage, and transcript document. Protected. | Path ID. | `204`. | `media.py:522-531`; media/document services/storage; no frontend control. | `curl -i -b "$COOKIE" -X DELETE "$BASE/media/$MEDIA_ID"` |

## Evaluation (5)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `POST /evaluation/datasets` | Create benchmark dataset. Protected. | `{knowledge_base_id,name,description?}`. | `201 DatasetRead`. | `evaluation.py:71-86`; `EvaluationService`; no creation UI. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"knowledge_base_id\":\"$KB_ID\",\"name\":\"Guide benchmark\"}" "$BASE/evaluation/datasets"` |
| `GET /evaluation/datasets` | List datasets. Protected. | None. | Array of `DatasetRead`. | `evaluation.py:89-103`; evaluation service/query; Evaluation/Feedback. | `curl -sS -b "$COOKIE" "$BASE/evaluation/datasets"` |
| `POST /evaluation/cases` | Add benchmark case. Protected. | `{dataset_id,question,expected_answer?,expected_citations?,language?,is_supported?}`. | `201 {id,status}`. | `evaluation.py:106-120`; evaluation service; no creation UI. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"dataset_id\":\"$DATASET_ID\",\"question\":\"What is the policy?\",\"expected_answer\":\"three days\",\"is_supported\":true}" "$BASE/evaluation/cases"` |
| `POST /evaluation/runs` | Run every case through RAG. Protected/generation-limited. | Query `dataset_id`. | `RunRead`. | `evaluation.py:123-176`; `EvaluationService.run_evaluation`; Evaluation. | `curl -sS -b "$COOKIE" -X POST "$BASE/evaluation/runs?dataset_id=$DATASET_ID"` |
| `GET /evaluation/runs` | List recent runs. Protected. | None. | Array of `RunRead`. | `evaluation.py:179-189`; database query; Evaluation. | `curl -sS -b "$COOKIE" "$BASE/evaluation/runs"` |

## Feedback (3)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `POST /feedback` | Store answer rating. Protected. | `{knowledge_base_id,question,answer,rating,category?,comment?,chat_message_id?,engine?,model_name?,latency_ms?}`. | `201 {id,status}`. | `feedback.py:34-52`; `FeedbackService`; client exists, no UI. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"knowledge_base_id\":\"$KB_ID\",\"question\":\"Guide question\",\"answer\":\"Guide answer\",\"rating\":\"unhelpful\",\"category\":\"missing_citation\"}" "$BASE/feedback"` |
| `GET /feedback/analytics` | Aggregate helpful/unhelpful/categories. Protected. | None. | `{total_feedback,helpful_count,unhelpful_count,helpful_rate,complaint_categories}`. | `feedback.py:55-60`; feedback service; Feedback page. | `curl -sS -b "$COOKIE" "$BASE/feedback/analytics"` |
| `POST /feedback/{feedback_id}/convert-to-eval` | Make an evaluation case. Protected. | `{dataset_id}`. | `201 {case_id,status}`. | `feedback.py:63-83`; feedback service; client imported but no UI action. | `curl -sS -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"dataset_id\":\"$DATASET_ID\"}" "$BASE/feedback/$FEEDBACK_ID/convert-to-eval"` |

## Templates and demo seed (3)

| Method and URL | Purpose / auth | Request | Success response | Handler / service / frontend | Manual curl |
|---|---|---|---|---|---|
| `GET /templates` | List fixed action templates. Protected. | None. | Array of `ActionTemplateRead`. | `templates.py:25-42`; `TemplateService`; Templates. | `curl -sS -b "$COOKIE" "$BASE/templates"` |
| `GET /templates/{template_id}` | Get one fixed template. Protected. | Path ID. | `ActionTemplateRead`. | `templates.py:45-54`; template service; page does not call detail. | `curl -sS -b "$COOKIE" "$BASE/templates/executive_summary"` |
| `POST /demo/seed` | Idempotently seed demonstration KB, ready documents/chat/evaluation data. Protected. | None. | `201 {status,knowledge_base_id,message}`. | `demo.py:60-264`; direct SQL/model helpers; client exists but no page control. | `curl -sS -b "$COOKIE" -X POST "$BASE/demo/seed"` |

## Important request and response notes

- Upload requests are multipart and are additionally constrained by middleware, storage streaming, quotas, media signatures, pages, and duration.
- Generation endpoints can return queue-busy or timeout errors even when ordinary GET endpoints are healthy.
- Background process endpoints return `202`; poll their detail/status route until `ready` or `failed`.
- `DocumentRead` and media read shapes expose safe status/warning/error fields. The media response excludes `technical_error_message` and cookie paths.
- Production frontend URLs are always same-origin `/api/v1` (`frontend/src/api/client.ts:27-38`). Development can use `VITE_API_BASE_URL`.
- Deleting a parent uses SQL foreign-key cascades where declared. Always test deletion in a disposable dataset before operational use.
