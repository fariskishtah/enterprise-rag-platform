# Hugging Face Docker Spaces Deployment Guide

EnterpriseRAG is pre-configured for single-container deployment on **Hugging Face Docker Spaces**.

---

## 1. Space Setup Instructions

1. Log in to [Hugging Face](https://huggingface.co/) and click **New Space**.
2. Name your Space: `enterprise-rag-platform` (or your choice).
3. Select License: **MIT**.
4. Select SDK: **Docker**.
5. Select Space Hardware: **CPU Basic** (Free, 2 vCPU, 16 GB RAM) or **CPU Upgrade**.
6. Set Privacy to **Public**.
7. Click **Create Space**.

---

## 2. Docker Space Configuration

The repository root includes a production multi-stage `Dockerfile` and `start-space.sh` entrypoint:
- **Port**: Bound to default port `7860`.
- **Runtime Profile**: Defaults to `APP_RUNTIME_PROFILE=huggingface_demo`.
- **Pre-installed System Binaries**: `ffmpeg`, `poppler-utils`, `tesseract-ocr`.

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
```

---

## 4. Cold-Start Behaviour & Model Caching

- On container boot, Qwen2.5-0.5B and MiniLM weights are loaded lazily on the first request (~5–10s cold-start).
- Subsequent requests execute in 2–4s using cached models in `/tmp/models`.
- To seed sample documents and evaluation datasets automatically for recruiters, click **Load Demo Workspace** in the UI (or trigger `POST /api/v1/demo/seed`).
