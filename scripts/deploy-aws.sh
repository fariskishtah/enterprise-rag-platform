#!/usr/bin/env bash
set -Eeuo pipefail

dry_run=0
if [[ ${1:-} == "--dry-run" ]]; then
  dry_run=1
elif [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--dry-run]" >&2
  exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${project_dir}/docker-compose.aws.yml"
environment_file="${project_dir}/.env"
cookie_file="/home/ubuntu/youtube-cookies.txt"
backup_dir="${ENTERPRISE_RAG_BACKUP_DIR:-/home/ubuntu/enterprise-rag-backups}"
export ENTERPRISE_RAG_BACKUP_DIR="${backup_dir}"

run() {
  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

require_env_value() {
  local key="$1"
  if ! awk -F= -v key="${key}" '$1 == key && length(substr($0, index($0, "=") + 1)) > 0 {found=1} END {exit !found}' "${environment_file}"; then
    echo "Required production setting ${key} is missing or blank in .env." >&2
    exit 1
  fi
}

command -v docker >/dev/null || { echo "Docker is required." >&2; exit 1; }
command -v curl >/dev/null || { echo "curl is required." >&2; exit 1; }
docker compose version >/dev/null
[[ -f ${environment_file} ]] || { echo "Create .env from .env.aws-cpu.example first." >&2; exit 1; }
[[ -f ${cookie_file} ]] || { echo "Missing read-only YouTube cookie source: ${cookie_file}" >&2; exit 1; }
[[ -r ${cookie_file} ]] || { echo "The YouTube cookie source is not readable." >&2; exit 1; }
require_env_value ENTERPRISE_RAG_DEMO_PASSWORD_HASH
require_env_value ENTERPRISE_RAG_SESSION_SECRET
docker compose -f "${compose_file}" config --quiet
if [[ ${dry_run} -eq 0 ]]; then
  mkdir -p "${backup_dir}"
  chmod 700 "${backup_dir}"
fi

commit="$(git -C "${project_dir}" rev-parse --verify HEAD)"
short_commit="$(git -C "${project_dir}" rev-parse --short=12 HEAD)"
export ENTERPRISE_RAG_GIT_COMMIT="${commit}"
previous_image=""
if docker inspect enterprise-rag >/dev/null 2>&1; then
  previous_image="$(docker inspect --format '{{.Image}}' enterprise-rag)"
fi
export ENTERPRISE_RAG_IMAGE_ID="${previous_image:-unknown}"
new_tag="release-${short_commit}-$(date -u +%Y%m%d%H%M%S)"

echo "Deploying EnterpriseRAG commit ${commit}"
echo "Creating a verified backup before the image build..."
run "${project_dir}/scripts/backup-production.sh"

export ENTERPRISE_RAG_IMAGE_TAG="${new_tag}"
echo "Building enterprise-rag:${new_tag}..."
run docker compose -f "${compose_file}" build app
run docker compose -f "${compose_file}" up -d --no-deps --force-recreate app

if [[ ${dry_run} -eq 1 ]]; then
  echo "Dry run complete; no backup, image, or container state was changed."
  exit 0
fi

healthy=0
for _attempt in {1..30}; do
  if curl --fail --silent http://127.0.0.1:7860/api/v1/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 2
done

if [[ ${healthy} -eq 1 ]]; then
  echo "Deployment health check passed for commit ${commit}."
  exit 0
fi

echo "New deployment failed its health check; restoring the previous image." >&2
if [[ -z ${previous_image} ]]; then
  echo "No previous container image was available for automatic rollback." >&2
  exit 1
fi
docker tag "${previous_image}" enterprise-rag:rollback
export ENTERPRISE_RAG_IMAGE_TAG=rollback
docker compose -f "${compose_file}" up -d --no-deps --force-recreate app
for _attempt in {1..30}; do
  if curl --fail --silent http://127.0.0.1:7860/api/v1/health >/dev/null; then
    echo "Previous image restored. The pre-upgrade backup remains in ${backup_dir}." >&2
    exit 1
  fi
  sleep 2
done

echo "Rollback container did not become healthy; use the restore runbook and verified backup." >&2
exit 1
