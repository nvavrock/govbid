#!/usr/bin/env bash
# Start Postgres + n8n + Adminer (uses WSL-safe Docker resolution).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"

govbid_resolve_docker >/dev/null || {
  echo "Docker unavailable. Run: bash scripts/ensure-docker.sh" >&2
  exit 1
}

if [[ -f .env ]]; then
  bash "$ROOT/scripts/generate-n8n-owner-hash.sh"
fi

echo "Using Docker: $GOVBID_DOCKER"
govbid_docker_compose up -d

if [[ -f .env ]]; then
  bash "$ROOT/scripts/sync-postgres-password.sh" >/dev/null 2>&1 || true
fi

bash "$ROOT/scripts/wait-n8n.sh" 60 >/dev/null 2>&1 || true

echo ""
echo "Services:"
echo "  n8n     http://localhost:5678"
echo "  Adminer http://localhost:8081"
