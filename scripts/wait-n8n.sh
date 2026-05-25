#!/usr/bin/env bash
# Wait until n8n container is running (not restarting).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"

govbid_resolve_docker >/dev/null

TRIES="${1:-30}"
for ((i = 1; i <= TRIES; i++)); do
  status="$(govbid_docker_compose ps n8n --format json 2>/dev/null | python3 -c "
import json,sys
raw=sys.stdin.read().strip()
if not raw:
    sys.exit(0)
rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
if not rows:
    print('missing')
else:
    print(rows[0].get('State','unknown'))
" 2>/dev/null || echo "unknown")"

  if [[ "$status" == "running" ]]; then
    echo "n8n is running."
    exit 0
  fi
  echo "Waiting for n8n ($i/$TRIES), state=$status..."
  sleep 2
done

echo "n8n did not become healthy. Check logs:" >&2
echo "  govbid_docker_compose logs n8n --tail 30" >&2
exit 1
