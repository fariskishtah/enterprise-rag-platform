#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${ENTERPRISE_RAG_COMPOSE_FILE:-${project_dir}/docker-compose.aws.yml}"
backup_dir="${ENTERPRISE_RAG_BACKUP_DIR:-/home/ubuntu/enterprise-rag-backups}"
export ENTERPRISE_RAG_BACKUP_DIR="${backup_dir}"

mkdir -p "${backup_dir}"
chmod 700 "${backup_dir}"
docker compose -f "${compose_file}" config --quiet
image_id="${ENTERPRISE_RAG_IMAGE_ID:-$(docker compose -f "${compose_file}" images -q app 2>/dev/null | head -n 1)}"

if docker compose -f "${compose_file}" ps --status running --services | grep -qx app; then
  docker compose -f "${compose_file}" exec -T \
    -e "ENTERPRISE_RAG_IMAGE_ID=${image_id:-unknown}" app \
    python3 /workspace/backend/scripts/production_backup.py backup --destination /backups
else
  docker compose -f "${compose_file}" run --rm --no-deps \
    -e "ENTERPRISE_RAG_IMAGE_ID=${image_id:-unknown}" \
    --entrypoint python3 app \
    /workspace/backend/scripts/production_backup.py backup --destination /backups
fi
