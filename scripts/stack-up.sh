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

echo "Using Docker: $GOVBID_DOCKER"
if ! govbid_docker_compose up -d; then
  # #region agent log
  _govbid_debug_log "E" "stack-up.sh" "compose_up_failed" "{}"
  # #endregion
  exit 1
fi
# #region agent log
_govbid_debug_log "E" "stack-up.sh" "compose_up_ok" "{\"docker\":\"${GOVBID_DOCKER//\"/\\\"}\"}"
# #endregion

if [[ -f .env ]]; then
  bash "$ROOT/scripts/sync-postgres-password.sh" >/dev/null 2>&1 || true
fi

echo ""
echo "Services:"
echo "  n8n     http://localhost:5678"
echo "  Adminer http://localhost:8081"
