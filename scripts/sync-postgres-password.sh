#!/usr/bin/env bash
# Align Postgres role password with POSTGRES_PASSWORD in .env (fixes n8n auth failures).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -f .env ]] || { echo "Missing .env" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

: "${POSTGRES_USER:?POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD}"

# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"
govbid_resolve_docker >/dev/null

govbid_docker_compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -v "pw=$POSTGRES_PASSWORD" \
  -c "ALTER USER :\"POSTGRES_USER\" WITH PASSWORD :'pw';" 2>/dev/null && {
  echo "Password synced for $POSTGRES_USER"
  exit 0
}

# Fallback without psql variables (older images)
escaped="${POSTGRES_PASSWORD//\'/\'\'}"
govbid_docker_compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -c "ALTER USER ${POSTGRES_USER} WITH PASSWORD '${escaped}';"
echo "Password synced for $POSTGRES_USER"
