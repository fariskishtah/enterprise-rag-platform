# AWS Lightsail CPU deployment

This profile targets Ubuntu with Docker, 2 vCPU, 4 GB RAM, and 4 GB swap. It keeps
generation serial, forces CPU inference, bounds context and output, and persists both
application data and downloaded Hugging Face models.

## Configure the server

Copy `.env.aws-cpu.example` to `.env`. The recommended multilingual embedding model is
`intfloat/multilingual-e5-small`; changing from `all-MiniLM-L6-v2` requires an explicit
document reindex. EnterpriseRAG rejects mixed-model vector searches and reports the
reindex requirement in Settings and `/api/v1/rag/config`.

Export YouTube cookies in Netscape cookie-file format on a trusted workstation, transfer
the file securely to `/home/ubuntu/youtube-cookies.txt`, and restrict access:

```bash
chmod 600 /home/ubuntu/youtube-cookies.txt
```

Cookie contents, tokens, raw headers, and the configured secret path are never returned by
the API. Refresh the file securely when YouTube expires the session. If cookies are not
available, remove `ENTERPRISE_RAG_YTDLP_COOKIES_FILE` and the cookie mount; ordinary
unauthenticated yt-dlp behavior remains enabled. Direct MP3, MP4, WAV, M4A, MOV, MKV, and
other supported uploads remain the reliable fallback.

The host file remains read-only inside the container. Immediately before yt-dlp runs, the
backend atomically copies it to `/tmp/enterprise-rag/youtube-cookies.txt`, restricts that
copy to mode `600`, and serializes yt-dlp jobs so yt-dlp can safely refresh its writable
cookie jar. The copy is replaced when the mounted source file's modification time changes;
cookie contents and both filesystem paths remain private. Update the host file atomically
when rotating cookies so the bind mount receives the new modification time.

## Build and run

```bash
docker build -t enterprise-rag:arabic-youtube-test .
docker run -d \
  --restart unless-stopped \
  --name enterprise-rag \
  -p 80:7860 \
  --env-file .env \
  -v enterprise-rag-data:/data \
  -v enterprise-rag-model-cache:/models \
  -v /home/ubuntu/youtube-cookies.txt:/run/secrets/youtube-cookies.txt:ro \
  enterprise-rag:arabic-youtube-test
```

Following the [official yt-dlp EJS guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS), the
production image includes Deno and the matching yt-dlp EJS package for YouTube's JavaScript
challenges. Verify the runtime after deployment:

```bash
docker exec enterprise-rag deno --version
docker exec enterprise-rag yt-dlp --version
```

After application startup has prepared the private runtime cookie copy, an operator can
perform a metadata-only diagnostic without making the secret mount writable:

```bash
docker exec enterprise-rag \
  yt-dlp --cookies /tmp/enterprise-rag/youtube-cookies.txt \
  --skip-download 'https://www.youtube.com/watch?v=jNQXAC9IVRw'
```

Use a URL you are authorized to access. Failures for a missing JavaScript solver, required
PO Token, unavailable audio/video formats, or expired cookies are terminal and sanitized.
YouTube increasingly requires per-video PO Tokens for some clients; when that applies,
follow the [official PO Token guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
to configure a maintained provider, or use direct media upload rather than placing a token
in application logs or source control.

The application starts with cold models by default so health checks are not held behind
downloads. Open Settings and select **Warm models** when controlled warm-up is appropriate,
or call `POST /api/v1/rag/warmup`. Warm-up loads embeddings first and generation second;
poll `/api/v1/rag/config` for `cold`, `loading`, `ready`, or `failed` status.

## Measured model choices

Benchmarks were run on 2026-07-27 on a local CPU-only macOS host in fresh Python processes;
Lightsail timings will differ. The committed scripts make the comparison repeatable.

| Embedding model | Fixture top-1 | Cached cold load + passages | Warm query mean | Peak RSS | Disk cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `all-MiniLM-L6-v2` | 1/3 | 9.83s | 6.47ms | 392 MB | 87 MB |
| `multilingual-e5-small` | 2/3 | 11.68s | 12.88ms | 593 MB | 470 MB |

The fixture covers Arabic-to-Arabic, Arabic-to-English, and English-to-Arabic retrieval.
E5 materially improved cross-language retrieval while remaining practical with serial model
use and swap. Its required `query:` and `passage:` prefixes are applied in both custom and
LangChain ingestion/query paths.

For a 12.4-second Arabic speech fixture with CPU `int8`, VAD, beam size 3, and two threads:

| faster-whisper model | Cached transcription | Peak RSS | Disk cache | Observed result |
| --- | ---: | ---: | ---: | --- |
| `base` | 5.61s | 486 MB | 141 MB | Two minor word-form errors |
| `small` | 8.52s | 527 MB | 464 MB | Corrected both word forms |

`base` is the AWS default because it was 34% faster and used substantially less disk. Keep
`small` available when Arabic accuracy is more important than latency and cache footprint.

At an equal 32-token bound, Qwen sampling versus the two-thread deterministic profile was:

| Case | Previous sampling | AWS deterministic |
| --- | ---: | ---: |
| Cold English | 127.66s | 94.01s |
| Warm English | 80.41s | 74.40s |
| Warm Arabic | 68.56s | 65.89s |
| Short summary | 66.47s | 69.77s |
| Peak RSS | 1,630 MB | 617 MB |

Deterministic decoding did not improve every warm case, so no blanket speed claim is made.
It reduced cold latency and peak RSS in this run and makes output reproducible. The AWS
profile additionally lowers the worst-case output bound from 128 to 96 tokens (25%) and
context from 4,000 to 3,000 characters; real answer latency remains workload-dependent.

Excluding CI-only `dev` dependencies from the production runtime reduced the measured ARM64
Docker image from 2.78 GB to 2.43 GB (350 MB, 12.7%). Streamlit remains installed by
`backend[dev]` for course/CI checks; the deployed application continues to serve React and
FastAPI with the complete media extra.

Repeat the measurements with:

```bash
backend/.venv/bin/python backend/scripts/benchmark_multilingual_retrieval.py \
  --model intfloat/multilingual-e5-small --cache backend/data/models
backend/.venv/bin/python backend/scripts/benchmark_transcription.py \
  --model base --media /path/to/arabic.wav --cache backend/data/models/whisper --language ar
backend/.venv/bin/python backend/scripts/benchmark_cpu_generation.py \
  --profile aws_cpu --cache backend/data/models --max-new-tokens 32
```

## Public-demo release procedure

The commands below assume the repository is checked out at
`/home/ubuntu/EnterpriseRAG`. They do not assume that you own a domain; replace
`demo.example.com` only after choosing one.

### 1. Prepare production configuration

```bash
cd /home/ubuntu/EnterpriseRAG
cp .env.aws-cpu.example .env
backend/.venv/bin/python backend/scripts/hash_demo_password.py
openssl rand -base64 48
```

Paste only the bcrypt result into `ENTERPRISE_RAG_DEMO_PASSWORD_HASH` and the independent
random value into `ENTERPRISE_RAG_SESSION_SECRET`. Keep `.env` mode 600 and never commit it:

```bash
chmod 600 .env
mkdir -p /home/ubuntu/enterprise-rag-backups
chmod 700 /home/ubuntu/enterprise-rag-backups
chmod 600 /home/ubuntu/youtube-cookies.txt
```

The tracked AWS example selects production `demo_password` access, secure cookies, a
120-minute session, 24-hour demo retention, 50 MB uploads, 300 pages, 30-minute media, five
knowledge bases, 25 files per knowledge base, one heavy operation, and a two-item queue.
Startup fails closed if the password hash or session secret is blank.

### 2. Build and start with Compose

The required YouTube secret mount remains exactly:

```text
-v /home/ubuntu/youtube-cookies.txt:/run/secrets/youtube-cookies.txt:ro
```

Compose expresses that same read-only mount and binds the application only to localhost:

```bash
export ENTERPRISE_RAG_BACKUP_DIR=/home/ubuntu/enterprise-rag-backups
docker compose -f docker-compose.aws.yml config --quiet
scripts/deploy-aws.sh --dry-run
scripts/deploy-aws.sh
curl --fail http://127.0.0.1:7860/api/v1/health
curl --fail http://127.0.0.1:7860/api/v1/readiness
```

The deployment script shows the commit, creates and verifies a backup, builds a commit-tagged
image, replaces only the application container, checks health for at most 60 seconds, and
recreates the previous image if health fails. It never runs `docker system prune`, removes
an image, or deletes a named volume.

Routine commands:

```bash
docker compose -f docker-compose.aws.yml build app
docker compose -f docker-compose.aws.yml up -d app
docker compose -f docker-compose.aws.yml stop --timeout 90 app
docker compose -f docker-compose.aws.yml restart app
docker compose -f docker-compose.aws.yml logs -f --tail=200 app
docker compose -f docker-compose.aws.yml ps
```

### 3. DNS, firewall, Nginx, and HTTPS

Allocate/attach a Lightsail static IP. At the DNS provider, create an `A` record for the
chosen hostname pointing to that static IP. Wait for propagation and verify both resolvers:

```bash
dig +short demo.example.com A
getent ahostsv4 demo.example.com
```

Do not run Certbot until those commands return the Lightsail static IP. In the Lightsail
networking firewall:

- restrict SSH 22 to your administration IP where practical;
- allow HTTP 80 for certificate issuance and redirect;
- allow HTTPS 443 publicly;
- remove any public rule for 7860; and
- keep Compose bound to `127.0.0.1:7860`.

Install Nginx and Certbot, copy the template, replace the placeholder hostname, and validate
before reload:

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo cp deploy/nginx/enterprise-rag.conf.template \
  /etc/nginx/sites-available/enterprise-rag
sudo sed -i 's/demo\.example\.com/YOUR_REAL_HOSTNAME/g' \
  /etc/nginx/sites-available/enterprise-rag
sudo ln -s /etc/nginx/sites-available/enterprise-rag \
  /etc/nginx/sites-enabled/enterprise-rag
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d YOUR_REAL_HOSTNAME --redirect
sudo certbot renew --dry-run
```

After HTTPS works, confirm `.env` still has `ENTERPRISE_RAG_COOKIE_SECURE=true`. Validate `/`,
`/login`, `/privacy`, `/terms`, `/security`, protected-route redirects, login/logout, direct
route refresh, and same-origin `/api/v1` browser requests.

### 4. Scheduled cleanup and backups

Preview cleanup without deleting anything:

```bash
docker compose -f docker-compose.aws.yml exec -T app \
  python3 /workspace/backend/scripts/cleanup_demo_data.py --dry-run
```

Install the service/timer units after reviewing paths:

```bash
sudo cp deploy/systemd/enterprise-rag.service.template \
  /etc/systemd/system/enterprise-rag.service
sudo cp deploy/systemd/enterprise-rag-cleanup.{service,timer} /etc/systemd/system/
sudo cp deploy/systemd/enterprise-rag-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now enterprise-rag.service
sudo systemctl enable --now enterprise-rag-cleanup.timer
sudo systemctl enable --now enterprise-rag-backup.timer
systemctl list-timers 'enterprise-rag-*'
```

Create and verify a backup manually:

```bash
scripts/backup-production.sh
scripts/verify-backup.sh \
  /home/ubuntu/enterprise-rag-backups/enterprise-rag-YYYYMMDDTHHMMSSZ
```

To test safely, restore only into a disposable Lightsail instance or disposable Docker data
volume created from a copied backup. Do not use the production volume for a practice restore.
For an actual authorized restore:

```bash
scripts/restore-production.sh \
  /home/ubuntu/enterprise-rag-backups/enterprise-rag-YYYYMMDDTHHMMSSZ --confirm
```

The restore script verifies the archive, creates a fresh pre-restore backup, stops the app,
restores SQLite/uploads, validates SQLite integrity and private permissions, restarts, and
checks health. If health fails, it leaves the app started for diagnosis and preserves both
backups.

### 5. Lightsail snapshots and rollback

Snapshots are a manual AWS control:

1. Create and verify an application backup.
2. In the Lightsail console, select the instance and open **Snapshots**.
3. Choose **Create snapshot**, name it with the UTC date and current git commit, and wait for
   completion.
4. Record the snapshot ID, backup ID, image tag, and commit in the private change record.
5. Retain at least the last known-good snapshot according to the project cost policy.
6. Test restoration on a new disposable instance before relying on the snapshot.

For an application-only rollback, tag the previous image as `enterprise-rag:rollback`, set
`ENTERPRISE_RAG_IMAGE_TAG=rollback`, and recreate `app`. If a migration/data restore is also
needed, use the verified backup workflow. Never delete named data/model volumes during
rollback.

### 6. Low-overhead operational checklist

Check this daily during a public launch and after every deployment:

- `docker stats --no-stream enterprise-rag` for CPU and memory;
- `free -h` for RAM and 4 GB swap pressure;
- `df -h / /var/lib/docker` for host and Docker disk;
- `docker inspect -f '{{.RestartCount}}' enterprise-rag` for restart count;
- `/api/v1/health` and `/api/v1/readiness` for failures;
- authenticated `/api/v1/operations/status` for model/queue/storage state;
- newest verified backup age and last cleanup result;
- `systemctl --failed` and timer status;
- Lightsail monthly cost and an AWS Budget alert configured manually.

Use Docker log rotation from Compose and systemd status instead of installing a heavyweight
metrics stack on the 4 GB host. Investigate sustained swap growth, disk below 15% free,
restarts above zero, repeated 503s, readiness failures, or a backup older than 26 hours.
