# Hugging Face Space Deployment Report

## Container & Build Specifications

- **Container Architecture**: Multi-stage single Docker container (Node 20 React build + Python 3.11-slim FastAPI backend).
- **Target Port**: `7860`.
- **Runtime Profile**: `APP_RUNTIME_PROFILE=huggingface_demo`.
- **Pre-installed System Binaries**: `ffmpeg`, `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-eng`, `tesseract-ocr-ara`.
- **Demo Workspace Seeder**: Endpoint `/api/v1/demo/seed` creates deterministic demo documents and evaluation datasets automatically.
- **Recommended Hardware**: Free CPU Basic (2 vCPU, 16 GB RAM) or CPU Upgrade.
