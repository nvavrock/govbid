#!/usr/bin/env bash
# Reset n8n persistent data when N8N_ENCRYPTION_KEY changed (fixes crash loop).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"

govbid_resolve_docker >/dev/null || {
  echo "Docker unavailable. Run: bash scripts/ensure-docker.sh" >&2
  exit 1
}

if [[ "${GOVBID_CONFIRM_RESET:-}" != "yes" ]]; then
  echo "This removes the n8n Docker volume (workflows, credentials, owner account in n8n)."
  echo "Re-run with:  GOVBID_CONFIRM_RESET=yes bash scripts/reset-n8n-volume.sh"
  exit 1
fi

echo "Stopping n8n..."
govbid_docker_compose stop n8n 2>/dev/null || true
govbid_docker_compose rm -f n8n 2>/dev/null || true

VOLUME="$(govbid_docker_compose config --format json 2>/dev/null | python3 -c "
import json,sys
cfg=json.load(sys.stdin)
vols=cfg.get('volumes',{})
for name, spec in vols.items():
    if name == 'n8n_data':
        print(name)
        break
" 2>/dev/null || true)"

# Compose prefixes volume: <project>_n8n_data
PROJECT="$(basename "$ROOT")"
FULL_VOLUME="${PROJECT}_n8n_data"

if docker volume inspect "$FULL_VOLUME" >/dev/null 2>&1; then
  echo "Removing volume: $FULL_VOLUME"
  docker volume rm "$FULL_VOLUME"
else
  echo "Volume $FULL_VOLUME not found (may already be clean)."
fi

echo "Starting n8n with encryption key from .env..."
govbid_docker_compose up -d n8n

echo ""
echo "Wait ~30s, then open http://localhost:5678 and complete owner setup."
echo "Then run: bash scripts/provision-n8n.sh"
