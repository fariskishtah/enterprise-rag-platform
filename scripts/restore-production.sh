#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 2 || "$2" != "--confirm" ]]; then
  echo "Usage: $0 /absolute/path/to/enterprise-rag-TIMESTAMP --confirm" >&2
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

"${project_dir}/scripts/verify-backup.sh" "${backup_path}"
echo "Creating the required pre-restore backup..."
"${project_dir}/scripts/backup-production.sh"

restart_required=1
on_exit() {
  if [[ ${restart_required} -eq 1 ]]; then
    docker compose -f "${compose_file}" up -d app || true
  fi
}
trap on_exit EXIT

docker compose -f "${compose_file}" stop --timeout 90 app
docker compose -f "${compose_file}" run --rm --no-deps \
  --entrypoint python3 app \
  /workspace/backend/scripts/production_backup.py restore \
  "/backups/$(basename "${backup_path}")" --confirm
docker compose -f "${compose_file}" up -d app

for _attempt in {1..30}; do
  if curl --fail --silent --show-error http://127.0.0.1:7860/api/v1/health >/dev/null; then
    restart_required=0
    trap - EXIT
    echo "Restore completed; application health check passed."
    exit 0
  fi
  sleep 2
done

echo "Restore completed but the application did not become healthy." >&2
exit 1
