#!/usr/bin/env bash
# Sync n8n owner password with .env (N8N_INSTANCE_OWNER_MANAGED_BY_ENV on n8n 2.17+).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"

[[ -f .env ]] || { echo "Missing .env" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

: "${N8N_BASIC_AUTH_PASSWORD:?Set N8N_BASIC_AUTH_PASSWORD in .env}"

govbid_resolve_docker >/dev/null || {
  echo "Docker unavailable." >&2
  exit 1
}

EMAIL="${N8N_OWNER_EMAIL:-nvavrock@gmail.com}"

echo "Updating n8n owner password for $EMAIL ..."
bash "$ROOT/scripts/generate-n8n-owner-hash.sh"
govbid_docker_compose restart n8n >/dev/null
bash "$ROOT/scripts/wait-n8n.sh" 60

echo "Done. Sign in at http://localhost:5678"
echo "  Email:    $EMAIL"
echo "  Password: N8N_BASIC_AUTH_PASSWORD in .env (or N8N_OWNER_PASSWORD if set)"
