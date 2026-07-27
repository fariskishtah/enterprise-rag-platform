# EnterpriseRAG public release checklist

`[MANUAL]` marks work that Codex cannot safely complete on the real AWS account/domain.

## Configuration

- [ ] Copy `.env.aws-cpu.example` to untracked `.env` on the server.
- [ ] Confirm `ENTERPRISE_RAG_ENVIRONMENT=production` and access mode `demo_password`.
- [ ] Validate Compose with `docker compose -f docker-compose.aws.yml config --quiet`.
- [ ] Confirm Docker binds only `127.0.0.1:7860`.

## Secrets and authentication

- [ ] [MANUAL] Enter a new bcrypt demo-password hash; never store plaintext.
- [ ] [MANUAL] Enter a unique random session secret of at least 32 characters.
- [ ] Set `.env` and the YouTube cookie file to mode 600.
- [ ] Verify valid login, generic invalid login, lockout, expiry, logout, and Secure/HttpOnly/SameSite cookie flags over HTTPS.
- [ ] Confirm protected pages/APIs reject unauthenticated requests while landing, login, health, readiness, and static assets remain public.

## Upload limits and rate limits

- [ ] Verify document/media size, MIME/extension/signature, page, and duration limits.
- [ ] Verify knowledge-base, files-per-base, request-body, concurrent-upload, and heavy-queue limits.
- [ ] Verify login, upload, generation, transcription, and URL-import rate limits return terminal errors.
- [ ] Confirm executable/unsupported archives and private URL targets are rejected.

## Database and storage

- [ ] Run the migration on a copied database and check `/api/v1/readiness`.
- [ ] Confirm named data and model-cache volumes survive container recreation.
- [ ] Confirm uploaded filenames are not used as server storage paths.
- [ ] Check free disk and Docker disk remain above the operational threshold.

## Backups and restore

- [ ] Run `scripts/backup-production.sh` and record the generated backup ID.
- [ ] Run `scripts/verify-backup.sh` on the new backup.
- [ ] Confirm backup files/directories are private and manifests contain no secret values.
- [ ] Test restore only on a disposable instance/volume; never use production for practice.
- [ ] Verify the real restore procedure creates a pre-restore backup, checks SQLite integrity, restarts, and health-checks.

## Cleanup and retention

- [ ] Run cleanup with `--dry-run` and review aggregate output.
- [ ] Confirm 24-hour expiry metadata is present on demo KBs/documents/media.
- [ ] Verify protected and active records survive cleanup.
- [ ] Enable and inspect the cleanup systemd timer.

## Domain, HTTPS, and firewall

- [ ] [MANUAL] Purchase/select the production domain.
- [ ] [MANUAL] Attach a Lightsail static IP and create the DNS A record.
- [ ] [MANUAL] Wait for and verify DNS propagation before Certbot.
- [ ] [MANUAL] Restrict SSH 22 where practical; expose only 80/443; remove public 7860.
- [ ] Validate Nginx syntax, body limit, proxy headers/timeouts, caching, and security headers.
- [ ] [MANUAL] Issue the certificate, enable redirect, and run `certbot renew --dry-run`.

## Health and monitoring

- [ ] Confirm health is lightweight and readiness checks database/schema/storage/cache/index paths.
- [ ] Confirm operations status is protected and does not expose paths or secrets.
- [ ] Verify structured request logs have request ID, path, method, status, and duration only.
- [ ] Inspect CPU, RAM, swap, disk, restart count, health failures, and backup age.
- [ ] [MANUAL] Configure the AWS monthly budget alert.

## Browser and API validation

- [ ] Run frontend unit tests and production Playwright smoke tests.
- [ ] Test landing, login/logout, dashboard, KBs, upload, chat, documents, media, intelligence, evaluation, feedback, templates, settings, privacy, terms, and security.
- [ ] Verify direct-route refresh and same-origin `/api/v1` requests.
- [ ] Verify success/error/timeout/abort paths clear spinners and polling is bounded.
- [ ] Verify no console errors, unhandled rejections, failed assets, or unexpected API failures.
- [ ] [MANUAL] Test desktop and mobile layouts on external devices.

## Arabic, document, and media acceptance

- [ ] Ask an Arabic question over English and/or Arabic source text and inspect RTL/citations.
- [ ] Ask an unsupported question and confirm insufficient evidence.
- [ ] Upload supported PDF, DOCX, and TXT fixtures; test malformed/oversized/page-limit errors.
- [ ] Upload a short direct Arabic MP3/MP4 and confirm transcript, timestamp, and terminal failure states.
- [ ] Treat YouTube as best-effort; do not repeat authentication attempts during release validation.

## Persistence, rollback, and snapshot

- [ ] Restart/recreate the app container and verify database/uploads/model cache persist.
- [ ] Test the image rollback workflow without deleting volumes.
- [ ] [MANUAL] Take and record the real Lightsail snapshot after backup verification.
- [ ] [MANUAL] Test snapshot restoration on a disposable instance.

## GitHub and presentation

- [ ] Review README claims, measured values, limitations, demo URL, and screenshots.
- [ ] Record the 90–120 second demo using non-sensitive fixtures.
- [ ] Review privacy, terms/demo notice, and security pages.
- [ ] Verify no `.env`, cookies, backups, databases, uploads, certificates, or model/test temp files are tracked.
- [ ] Confirm CI, deterministic tests, Ruff, Compose, shell, Nginx, Docker, and Playwright results in the release report.
