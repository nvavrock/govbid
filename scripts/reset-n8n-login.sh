#!/usr/bin/env bash
# Reset n8n owner password to match N8N_BASIC_AUTH_PASSWORD in .env (or set a new one).
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
NEW_PASS="${N8N_OWNER_PASSWORD:-$N8N_BASIC_AUTH_PASSWORD}"

echo "Setting n8n password for $EMAIL ..."
HASH="$(govbid_docker_compose exec -T n8n node -e \
  "const b=require('/usr/local/lib/node_modules/n8n/node_modules/bcryptjs');console.log(b.hashSync(process.argv[1],10))" \
  "$NEW_PASS" 2>/dev/null | tr -d '\r\n')"

if [[ -z "$HASH" || "$HASH" != \$2a\$* ]]; then
  echo "Failed to generate password hash. Is n8n running?" >&2
  exit 1
fi

govbid_docker_compose exec -T postgres psql -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" \
  -c "UPDATE \"user\" SET password = '$HASH' WHERE email = '$EMAIL';" >/dev/null

echo "Done. Sign in at http://localhost:5678"
echo "  Email:    $EMAIL"
echo "  Password: value of N8N_BASIC_AUTH_PASSWORD in .env (or N8N_OWNER_PASSWORD if set)"
