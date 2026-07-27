# Security model for the public demo

This document describes controls implemented in the repository. It is not a claim of
penetration testing, compliance certification, independent audit, privacy guarantee, or
fitness for regulated data.

## Access control

`ENTERPRISE_RAG_ACCESS_MODE` supports:

- `open` for local development;
- `demo_password` for the AWS public demo; and
- `accounts` as the boundary for the existing account API, not a full identity platform.

The AWS example defaults to `demo_password` and refuses production startup unless a bcrypt
password hash and a session secret of at least 32 characters are supplied. Successful
login creates a signed, expiring HttpOnly, SameSite=Lax cookie. `Secure=true` is required in
the AWS example. Unsafe cookie-authenticated requests reject cross-site browser requests.
Login errors are generic, failed attempts are bounded, and temporary lockout uses a hashed
IP/User-Agent fingerprint. Logout clears the cookie.

All SPA and API routes require authentication except `/`, `/login`, `/privacy`, `/terms`,
`/security`, static assets, health/readiness, and the authentication bootstrap endpoints.
The production `accounts` mode still needs a product-specific authorization and tenant
model before it can be called multi-tenant.

## Upload and URL controls

- Server-generated UUID storage names and resolved-path containment prevent client filename
  traversal.
- PDF, TXT, DOCX, and supported media types have extension, content, size, and signature
  checks. DOCX archives have member, uncompressed-size, compression-ratio, and internal-path
  bounds.
- Media duration and stream validity are probed before transcription.
- Executable and unsupported archive extensions are rejected.
- URL imports allow HTTP(S), reject URL credentials and private/reserved/link-local targets,
  revalidate redirects, cap redirects and bytes, and apply network timeouts.
- Read-only YouTube cookie secrets are copied atomically to a mode-600 runtime file and
  cookie content is never logged or returned.

Malware scanning and isolated media workers are not implemented; public users must not
upload untrusted confidential material.

## Resource controls

Request body size, upload size, page count, media duration, knowledge-base/file quotas,
upload concurrency, and per-route request rates are bounded. Qwen generation, summaries,
reports, warm-up, and media transcription share one process-level heavy-operation gate on
AWS. Its waiting queue is bounded and a full/busy server returns an actionable 429 or 503.
Timed-out or cancelled thread work retains its slot until the worker exits.

The limiter and queue are process-local. They are appropriate for one demo container and
must be replaced with durable shared coordination before horizontal scaling.

## Prompt and output handling

Retrieved passages are labelled as untrusted source context. Model and document strings are
rendered by React as text; the frontend does not use `dangerouslySetInnerHTML`. Citation
support checks and insufficient-evidence behavior reduce unsupported answers but do not
guarantee correctness or prevent every prompt-injection technique.

## Logging and operations

HTTP logs are JSON and contain request ID, path, method, response status, and duration. The
middleware never logs request bodies, passwords, authorization headers, cookies, document
contents, or YouTube cookie contents. User-visible exceptions use safe envelopes and media
technical details remain server-side.

`/api/v1/health` and `/api/v1/readiness` are public and contain no secrets.
`/api/v1/operations/status` is protected and exposes only bounded operational state,
configured limits, capacity, disk totals, and safe cleanup/backup results.

## Data lifecycle and recovery

Demo knowledge bases, documents, and media store creation, last-access, and optional expiry
timestamps. Cleanup skips protected records and active jobs, resolves every deletion below
the configured upload root, ignores model/database paths, supports dry-run, and records only
safe aggregate results.

Backups use SQLite's online backup API, archive the application data root, omit secret
values, record commit/image metadata, store files mode 600, verify SHA-256 checksums and tar
paths, and retain seven days by default. Restore requires explicit confirmation and the
shell workflow creates a separate pre-restore backup before stopping the application.

## Deployment boundary

Nginx terminates HTTPS and proxies to Docker on `127.0.0.1:7860`. The template configures a
55 MB body limit, bounded proxy timeouts, forwarded protocol/IP headers, static caching,
no-store API responses, and browser security headers. Port 7860 should not be open in the
Lightsail firewall. Production secrets belong only in untracked `.env`/secret files.

## Reporting vulnerabilities

Use the GitHub security/contact path described in [`../SECURITY.md`](../SECURITY.md). Do not
include credentials, cookie files, private uploads, or production database content in an
issue.
