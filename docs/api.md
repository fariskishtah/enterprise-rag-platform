# API notes

FastAPI publishes the complete OpenAPI contract at `/docs` and `/openapi.json`.

Grounded answer responses retain the compatible `answer` field and add typed
`direct_answer`, `supporting_explanation`, citations, confidence, support status,
not-found, retrieved chunk IDs, generation model, and response time. Debug mode adds
rewritten query, bounded context, model names, stage timings, fusion strategy, and
per-source dense/lexical/reranking scores.

`POST /knowledge-bases/{id}/ask` accepts `response_mode` (`concise` or `detailed`) and
optional `source_document_ids`. The media convenience route automatically restricts the
same service to its transcript document.

Media lifecycle is visible from `GET /media/{id}`. Transcript pagination uses `offset`
and `limit`; transcript search is `GET /media/{id}/transcript/search?query=...`.
Exports are `transcript.txt`, `transcript.md`, `transcript.json`, and `summary.md`.

All expected failures use:

```json
{"error": {"code": "stable_machine_code", "message": "Safe user message"}}
```

Debug-only technical failures are persisted in bounded database fields and are not
returned by the public media schema.
