#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/enterprise-rag-TIMESTAMP" >&2
  exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${ENTERPRISE_RAG_COMPOSE_FILE:-${project_dir}/docker-compose.aws.yml}"
backup_dir="${ENTERPRISE_RAG_BACKUP_DIR:-/home/ubuntu/enterprise-rag-backups}"
backup_path="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
case "${backup_path}" in
  "${backup_dir}"/enterprise-rag-*) ;;
  *) echo "Backup must be a generated directory inside ${backup_dir}." >&2; exit 2 ;;
esac
export ENTERPRISE_RAG_BACKUP_DIR="${backup_dir}"

docker compose -f "${compose_file}" run --rm --no-deps \
  --entrypoint python3 app \
  /workspace/backend/scripts/production_backup.py verify "/backups/$(basename "${backup_path}")"
