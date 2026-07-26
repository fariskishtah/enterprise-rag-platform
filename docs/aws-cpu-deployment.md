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
