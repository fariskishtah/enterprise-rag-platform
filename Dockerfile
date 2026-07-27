# ──────────────────────────────────────────────────────────────────────
# EnterpriseRAG — Single-Container Hugging Face Docker Space Build
# ──────────────────────────────────────────────────────────────────────

# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# yt-dlp recommends Deno >=2.3 for YouTube's external JavaScript challenges.
# The official bin image is multi-architecture and contributes only the runtime binary.
FROM denoland/deno:bin-2.9.4 AS deno-runtime

# Stage 2: Python Backend Runtime
FROM python:3.11-slim AS runtime

COPY --from=deno-runtime /deno /usr/local/bin/deno
RUN deno --version

# Install system dependencies (ffmpeg for media, poppler for PDF images, tesseract for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ara \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install Python backend
COPY backend/pyproject.toml /workspace/backend/
COPY backend/app /workspace/backend/app
COPY backend/alembic.ini /workspace/backend/alembic.ini
COPY backend/migrations /workspace/backend/migrations
COPY backend/scripts /workspace/backend/scripts
# The production image runs on CPU. Installing torch from the default PyPI
# index pulls the full CUDA runtime on Linux, even for CPU-only hosts.
ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir 'torch>=2.7,<3.0' --index-url "${PYTORCH_INDEX_URL}"
# Development-only tools (pytest, Ruff, Streamlit course demo) stay in CI and are
# intentionally excluded from the deployed React/FastAPI runtime.
RUN pip install --no-cache-dir -e '/workspace/backend[media]'

# Copy frontend static build artifacts into backend static directory
COPY --from=frontend-builder /build/dist /workspace/backend/app/static

# Copy root scripts and startup configurations
COPY start-space.sh /workspace/start-space.sh
RUN chmod +x /workspace/start-space.sh /workspace/backend/scripts/*.py

# Environment settings for Hugging Face Docker Space
ENV APP_RUNTIME_PROFILE=huggingface_demo \
    PYTHONUNBUFFERED=1 \
    CUDA_VISIBLE_DEVICES="" \
    TOKENIZERS_PARALLELISM=false \
    DENO_DIR=/tmp/enterprise-rag/deno-cache \
    PORT=7860 \
    ENTERPRISE_RAG_DATABASE_URL=sqlite:////tmp/enterprise_rag.db \
    ENTERPRISE_RAG_STORAGE_PATH=/tmp/uploads \
    ENTERPRISE_RAG_MODEL_CACHE_PATH=/tmp/models

EXPOSE 7860

ENTRYPOINT ["/workspace/start-space.sh"]
