# 08 — Deployment guide

## What is actually tracked

The repository implements a single-instance public demo behind Nginx and HTTPS (`docs/deployment.md:1-16`). It provides:

- a multi-stage production `Dockerfile`;
- `docker-compose.aws.yml` for a loopback-only app, persistent data/model volumes, backup bind, read-only cookie source, healthcheck, limits, and log rotation;
- an Nginx **HTTP template** with placeholder `demo.example.com`;
- instructions to use Certbot to add HTTPS/redirect after DNS works (`docs/aws-cpu-deployment.md:200-239`);
- systemd app, hourly cleanup, and daily backup units;
- health-gated deploy/rollback and verified backup/restore scripts.

The repository contains no `duckdns`, DuckDNS hostname, DuckDNS updater, account/token, or live DNS configuration. The current public domain, IP record, certificate, AWS instance, installed Nginx file, firewall, and systemd state are **Not verified from the current codebase.** DuckDNS can be used as the external DNS provider, but it is an operator-owned layer outside this repository.

## Intended production request path

```text
Browser
  -> DuckDNS (or another DNS provider): hostname resolves to server public/static IP
  -> HTTPS on port 443: certificate handled by Nginx/Certbot on the host
  -> Nginx: proxy and security/body/timeout policy
  -> 127.0.0.1:7860: Docker-published loopback port
  -> enterprise-rag container, Uvicorn/FastAPI
       ├─ /assets/*        -> compiled React assets
       ├─ /api/v1/*        -> FastAPI routes/services/models
       └─ other safe paths -> React index.html SPA fallback
          ├─ /data/enterprise_rag.db and uploads/derived data
          ├─ /models/huggingface model cache
          ├─ /tmp/enterprise-rag writable cookie/Deno/processing runtime
          └─ /backups host bind for verified backup sets
```

### 1. Browser and same-origin frontend

The production React bundle always sends API requests to relative `/api/v1` (`frontend/src/api/client.ts:27-38`). This avoids hard-coded development/AWS origins and lets cookies use the same origin. Normal pages are browser routes; API and assets are server routes.

### 2. DuckDNS or other DNS

DNS translates a hostname into the server's public IP. If the operator chooses DuckDNS, create/update the DuckDNS record outside the application and confirm it resolves to the attached AWS/Lightsail static IP. The generic repository instructions use an A record and `dig`/`getent` (`docs/aws-cpu-deployment.md:200-210`).

Do not request a certificate until public DNS returns the correct IP. A live DuckDNS update mechanism is **Not verified from the current codebase.** If the instance IP can change, use a static IP or an independently secured/monitored updater.

### 3. HTTPS certificate

The tracked Nginx template listens on port 80 only (`deploy/nginx/enterprise-rag.conf.template:1-5`). Repository instructions install Certbot's Nginx integration and run:

```bash
sudo certbot --nginx -d YOUR_REAL_HOSTNAME --redirect
sudo certbot renew --dry-run
```

Certbot is expected to create/manage the port-443 certificate and HTTP redirect in the installed host configuration (`docs/aws-cpu-deployment.md:219-239`). The certificate files are not stored in this repository. After HTTPS works, `ENTERPRISE_RAG_COOKIE_SECURE=true` must remain enabled.

### 4. Nginx

`deploy/nginx/enterprise-rag.conf.template`:

- proxies `/api/v1/health` to loopback with low logging (`:15-21`);
- caches proxied `/assets/` for one year (`:23-27`);
- proxies `/api/` with 10-second connect and 240-second send/read timeouts and `no-store` (`:29-49`);
- proxies all other paths with a 60-second read timeout (`:51-60`);
- limits bodies to 55 MB and adds content-type, frame, referrer, permissions, and CSP headers (`:6-13`).

Replace `demo.example.com` only after choosing the real hostname, test with `nginx -t`, and keep the application port private. The template trusts only the client address Nginx observes for `X-Forwarded-For`, rather than a client-supplied chain (`:33-37`).

### 5. Docker and FastAPI

The Dockerfile has three logical pieces:

1. Node 20 builds the React bundle (`Dockerfile:5-11`).
2. The official Deno binary stage supplies Deno 2.9.4 for supported yt-dlp JavaScript challenges (`:13-21`).
3. Python 3.11 slim installs ffmpeg, Poppler, Tesseract English/Arabic, CPU PyTorch, and `backend[media]`; copies React output into `backend/app/static`; then runs `start-space.sh` (`:17-70`).

`start-space.sh` creates `/tmp` directories, applies Alembic migrations, and starts one Uvicorn process on `0.0.0.0:7860` (`start-space.sh:6-15`). `create_app` exposes the API and mounts `/assets`; its safe SPA fallback returns static files where present and `index.html` for frontend paths, but rejects missing `/api/` paths (`backend/app/main.py:206-224`).

## Persistent and temporary paths

| Logical data | Container path / source | Persistence | Responsible files |
|---|---|---|---|
| SQLite, uploads, derived files, LangChain indexes as configured | `/data` named volume in AWS profile | Persistent across container recreation | `.env.aws-cpu.example`; `docker-compose.aws.yml:18-20`; settings/storage/migrations |
| Hugging Face models | `/models/huggingface` named volume | Persistent cache | `docker-compose.aws.yml:14,20`; model providers |
| Host YouTube cookie source | `/run/secrets/youtube-cookies.txt:ro` | Host-owned read-only bind | `docker-compose.aws.yml:21`; media cookie preparation |
| Writable runtime cookie copy | `/tmp/enterprise-rag/youtube-cookies.txt` | Container temporary; mode 0600 | `backend/app/services/media.py:197-245` |
| Deno cache / processing temp | `/tmp/enterprise-rag/...` | Container temporary | Docker `DENO_DIR`; media service |
| Verified backups | `/backups` container bind to host backup directory | Host persistent | `docker-compose.aws.yml:12,22`; backup scripts |
| Compiled React | `/workspace/backend/app/static` | Immutable image content | `Dockerfile:50-51`; `main.py:208-224` |

The simple Dockerfile defaults use `/tmp` for a Hugging Face Space. The AWS `.env` must override database/storage/cache paths to persistent mounts. Do not assume `/tmp` survives a restart.

## AWS Compose behavior

`docker-compose.aws.yml:1-47` runs one service:

- `127.0.0.1:7860:7860`, so Nginx can reach it but the internet cannot directly reach 7860;
- named `enterprise-rag-data` and `enterprise-rag-model-cache` volumes;
- exact read-only cookie mount:

  ```text
  -v /home/ubuntu/youtube-cookies.txt:/run/secrets/youtube-cookies.txt:ro
  ```

- backup host bind, health check, 10 MB x 3 JSON logs, 90-second stop grace;
- no-new-privileges, all Linux capabilities dropped, 3200 MB memory, 2 CPUs, and 512 PIDs.

The Dockerfile does not declare a non-root `USER`; this risk is discussed separately even though capabilities and privileges are constrained.

## Release procedure

### Prepare

On the intended Ubuntu host, review `docs/aws-cpu-deployment.md` in full. Its tracked path assumption is `/home/ubuntu/EnterpriseRAG`. At minimum:

1. Copy `.env.aws-cpu.example` to untracked `.env`.
2. Generate a bcrypt demo hash and a separate random 32+ character session secret. Keep `.env` mode 0600.
3. Create the backup directory mode 0700.
4. If YouTube cookies are enabled, securely place the Netscape cookie file at `/home/ubuntu/youtube-cookies.txt`, mode 0600. Never print it.
5. Validate Compose and run the deployment dry run.

```bash
export ENTERPRISE_RAG_BACKUP_DIR=/home/ubuntu/enterprise-rag-backups
docker compose -f docker-compose.aws.yml config --quiet
scripts/deploy-aws.sh --dry-run
```

### Deploy

```bash
scripts/deploy-aws.sh
curl --fail http://127.0.0.1:7860/api/v1/health
curl --fail http://127.0.0.1:7860/api/v1/readiness
```

`scripts/deploy-aws.sh:37-106` checks tools/config/cookie/secrets, records the current commit, creates a verified backup, builds a unique image tag, replaces only the app, waits up to 60 seconds for health, and recreates the previous image if the new image fails. It does not prune Docker or remove volumes.

### Install host proxy and timers

Review and replace placeholders before copying templates. The repository instructions install/reload Nginx, obtain/renew-test the certificate, and enable:

- `enterprise-rag.service` — Compose app;
- `enterprise-rag-cleanup.timer` — hourly cleanup with randomized delay;
- `enterprise-rag-backup.timer` — daily at 02:15 UTC with randomized delay.

The exact commands are at `docs/aws-cpu-deployment.md:219-261`; unit contents are under `deploy/systemd/`.

## Backup and restore architecture

The daily/manual backup is not a raw uncoordinated copy. The scripts create a SQLite-safe snapshot, collect required persistent application data, write a secret-free environment template and manifest/checksums, apply private permissions, verify the result, and retain according to settings (`scripts/backup-production.sh`; `scripts/verify-backup.sh`).

Restore requires both a backup path inside the configured root and literal `--confirm`. It verifies first, creates a pre-restore backup, stops the app, restores, restarts, and checks health (`scripts/restore-production.sh:4-49`). Practice restore only on a disposable instance/volume.

Backups remain on the same host unless an operator copies/encrypts them elsewhere. Off-site storage, backup encryption, and key rotation are **Not verified from the current codebase.**

## Rollback

There are two different problems:

- **Bad application image, compatible data:** `deploy-aws.sh` can recreate the previous image automatically after failed health.
- **Data/schema damage:** use a verified application backup through the explicit restore procedure. A prior image alone does not reverse database changes safely.

Lightsail snapshots are a manual external control described at `docs/aws-cpu-deployment.md:286-301`; snapshot existence and restoration testing are **Not verified from the current codebase.**

## Post-deploy acceptance checks

1. DNS resolves only to the intended static/public IP.
2. HTTP redirects to HTTPS; certificate hostname/expiry are valid; renewal dry-run passes.
3. Public ports are 80/443, administration as restricted, and 7860 is not public.
4. `/`, `/login`, legal pages, protected redirect/login/logout, assets, APIs, and dynamic direct-route refresh work.
5. Browser network requests use same-origin `/api/v1`; no console errors or authentication loop.
6. `/health` and `/readiness` are 200; authenticated `/operations/status` has correct build/profile/path health without secrets.
7. `docker exec enterprise-rag deno --version`, ffmpeg, and yt-dlp version checks work.
8. Direct document and media workflows complete. Test YouTube only with authorized content and current cookies; direct upload remains fallback.
9. Cleanup dry-run is reasonable; timers are active; newest backup verifies; a restore has been rehearsed on disposable infrastructure.
10. Check memory/swap/disk/restart count and logs as listed at `docs/aws-cpu-deployment.md:303-319`.

## Deployment boundaries

This architecture is a small, single-container, single-instance demo. It does not provide independently scalable workers, distributed queues/rate limits, managed PostgreSQL, object storage, active-active failover, or built-in off-site backups (`docs/deployment.md:15-16`). Treat migration to those systems as a new architecture project, not a configuration toggle.
