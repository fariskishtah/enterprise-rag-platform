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

# Stage 2: Python Backend Runtime
FROM python:3.11-slim AS runtime

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
COPY backend/pyproject.toml backend/README.md /workspace/backend/
COPY backend/app /workspace/backend/app
RUN pip install --no-cache-dir -e '/workspace/backend[dev,media]'

# Copy frontend static build artifacts into backend static directory
COPY --from=frontend-builder /build/dist /workspace/backend/app/static

# Copy root scripts and startup configurations
COPY start-space.sh /workspace/start-space.sh
RUN chmod +x /workspace/start-space.sh

# Environment settings for Hugging Face Docker Space
ENV APP_RUNTIME_PROFILE=huggingface_demo \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    ENTERPRISE_RAG_DATABASE_URL=sqlite:////tmp/enterprise_rag.db \
    ENTERPRISE_RAG_STORAGE_PATH=/tmp/uploads \
    ENTERPRISE_RAG_MODEL_CACHE_PATH=/tmp/models

EXPOSE 7860

ENTRYPOINT ["/workspace/start-space.sh"]
