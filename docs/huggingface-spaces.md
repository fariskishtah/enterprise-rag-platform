# Hugging Face Docker Spaces Deployment Guide

EnterpriseRAG is pre-configured for single-container deployment on **Hugging Face Docker Spaces**.

---

## 1. Space Setup Instructions

1. Log in to [Hugging Face](https://huggingface.co/) and click **New Space**.
2. Name your Space: `enterprise-rag-platform` (or your choice).
3. Select License: **MIT**.
4. Select SDK: **Docker**.
5. Select CPU hardware with enough memory for the configured local models.
6. Set Privacy to **Public**.
7. Click **Create Space**.

---

## 2. Docker Space Configuration

The repository root includes a production multi-stage `Dockerfile` and `start-space.sh` entrypoint:
- **Port**: Bound to default port `7860`.
- **Runtime Profile**: Defaults to `APP_RUNTIME_PROFILE=huggingface_demo`.
- **Pre-installed System Binaries**: `ffmpeg`, `poppler-utils`, `tesseract-ocr`, and Deno.

---

## 3. Recommended Space Environment Variables

Set these in your Space **Settings -> Variables**:

```env
APP_RUNTIME_PROFILE=huggingface_demo
RAG_ENGINE=custom
ENTERPRISE_RAG_GENERATION_MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct
ENTERPRISE_RAG_EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
ENTERPRISE_RAG_MAX_CONCURRENT_GENERATIONS=1
ENTERPRISE_RAG_GENERATION_TIMEOUT_SECONDS=45
ENTERPRISE_RAG_ENVIRONMENT=production
ENTERPRISE_RAG_ACCESS_MODE=demo_password
ENTERPRISE_RAG_DEMO_PASSWORD_HASH=<bcrypt hash stored as a Space secret>
ENTERPRISE_RAG_SESSION_SECRET=<unique random value stored as a Space secret>
ENTERPRISE_RAG_COOKIE_SECURE=true
```

---

## 4. Cold-Start Behaviour & Model Caching

- Model weights load lazily and may first need to download. Cold-start and generation time
  depend on the selected Space hardware and are not guaranteed.
- The default `/tmp/models` cache is ephemeral across container replacement unless the Space
  is configured with suitable persistent storage.
- An authenticated operator can trigger `POST /api/v1/demo/seed` to create the two real TXT
  sample files and unscored evaluation cases described in the demo data guide.
