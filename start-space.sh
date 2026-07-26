#!/usr/bin/env bash
set -e

echo "Starting EnterpriseRAG Hugging Face Space Runtime..."

# Ensure tmp directories exist
mkdir -p /tmp/uploads /tmp/models /tmp/data

# Run python server with static file serving on port 7860
cd /workspace/backend
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 7860
