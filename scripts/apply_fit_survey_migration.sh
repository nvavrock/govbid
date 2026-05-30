#!/usr/bin/env bash
# Apply db/migrations/004_fit_surveys.sql to an existing Postgres (initdb only runs 001/002 on fresh volumes).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -f .env ]] || { echo "Missing .env" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"
govbid_resolve_docker >/dev/null

echo "Applying db/migrations/004_fit_surveys.sql ..."
govbid_docker_compose exec -T postgres psql -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" \
  < "$ROOT/db/migrations/004_fit_surveys.sql"

echo "Done."

