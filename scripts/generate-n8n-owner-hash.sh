#!/usr/bin/env bash
# Ensure N8N_INSTANCE_OWNER_PASSWORD_HASH in .env matches owner password (bcrypt).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"

[[ -f .env ]] || { echo "Missing .env — run: cp .env.example .env" >&2; exit 1; }

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${N8N_BASIC_AUTH_PASSWORD:?Set N8N_BASIC_AUTH_PASSWORD in .env}"

govbid_resolve_docker >/dev/null || {
  echo "Docker unavailable. Run: bash scripts/ensure-docker.sh" >&2
  exit 1
}

N8N_TAG="$(grep -E '^\s*image:\s*n8nio/n8n:' docker-compose.yml | head -1 | sed -E 's/.*n8nio\/n8n://; s/[[:space:]]+$//')"
: "${N8N_TAG:?Could not read n8n image tag from docker-compose.yml}"

OWNER_PASS="${N8N_OWNER_PASSWORD:-$N8N_BASIC_AUTH_PASSWORD}"
N8N_IMAGE="n8nio/n8n:${N8N_TAG}"

hash_matches() {
  local pass="$1" hash="$2"
  govbid_docker run --rm --entrypoint node "$N8N_IMAGE" -e \
    "const b=require('/usr/local/lib/node_modules/n8n/node_modules/bcryptjs');process.exit(b.compareSync(process.argv[1], process.argv[2])?0:1)" \
    "$pass" "$hash" >/dev/null 2>&1
}

if [[ -n "${N8N_INSTANCE_OWNER_PASSWORD_HASH:-}" ]] && hash_matches "$OWNER_PASS" "$N8N_INSTANCE_OWNER_PASSWORD_HASH"; then
  echo "OK   N8N_INSTANCE_OWNER_PASSWORD_HASH matches password"
  exit 0
fi

echo "Generating N8N_INSTANCE_OWNER_PASSWORD_HASH ..."
NEW_HASH="$(govbid_docker run --rm --entrypoint node "$N8N_IMAGE" -e \
  "const b=require('/usr/local/lib/node_modules/n8n/node_modules/bcryptjs');console.log(b.hashSync(process.argv[1],10))" \
  "$OWNER_PASS" 2>/dev/null | tr -d '[:space:]')"

if [[ -z "$NEW_HASH" || "$NEW_HASH" != \$2a\$* ]]; then
  echo "Failed to generate bcrypt hash (${N8N_IMAGE})." >&2
  exit 1
fi

python3 - "$NEW_HASH" <<'PY'
import re
import sys
from pathlib import Path

hash_val = sys.argv[1]
path = Path(".env")
content = path.read_text(encoding="utf-8")
key = "N8N_INSTANCE_OWNER_PASSWORD_HASH"
line = f"{key}='{hash_val}'"
if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
    content = re.sub(rf"^{re.escape(key)}=.*$", line, content, flags=re.MULTILINE)
else:
    content = content.rstrip() + "\n" + line + "\n"
path.write_text(content, encoding="utf-8")
PY

echo "Updated .env with N8N_INSTANCE_OWNER_PASSWORD_HASH"
