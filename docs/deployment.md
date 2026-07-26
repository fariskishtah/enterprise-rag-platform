# Deployment notes

The included profile is intentionally local and single-tenant. Before network exposure:

- add authentication, RBAC, authorization on every knowledge-base lookup, and tenant keys;
- replace in-process tasks with a durable queue and idempotency/lease control;
- use managed PostgreSQL and pgvector plus durable object storage;
- terminate TLS and apply request/body/rate limits at an ingress;
- isolate ffmpeg/yt-dlp/transcription workers with CPU, memory, network, and time limits;
- use signed media URLs, malware scanning, audit logs, retention, backups, and a secrets
  manager;
- split CPU generation and GPU transcription into independently scalable worker pools;
- add health/readiness checks for database, model cache, ffmpeg, and queue dependencies.

Do not mount model or upload directories world-readable. Keep temporary storage on an
encrypted volume and configure lifecycle cleanup.
