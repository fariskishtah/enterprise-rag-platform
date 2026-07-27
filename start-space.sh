#!/usr/bin/env bash
set -e

echo "Starting EnterpriseRAG Hugging Face Space Runtime..."

# Ensure tmp directories exist
mkdir -p /tmp/uploads /tmp/models /tmp/data

# Apply the current schema before accepting traffic. The deploy workflow creates
# a verified backup before replacing the running container.
cd /workspace/backend
python3 /workspace/backend/scripts/migrate_database.py

# Run python server with static file serving on port 7860
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 7860
