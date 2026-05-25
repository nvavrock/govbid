#!/usr/bin/env bash
# Run a saved query from db/queries/ against govbid Postgres.
# Usage: bash scripts/run-query.sh <name>
#   name = filename without .sql (e.g. review_queue, sanity_counts)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/run-query.sh <query-name>" >&2
  echo "Available queries:" >&2
  for f in db/queries/*.sql; do
    echo "  $(basename "$f" .sql)" >&2
  done
  exit 1
fi

NAME="${1%.sql}"
QUERY_FILE="db/queries/${NAME}.sql"

if [[ ! -f "$QUERY_FILE" ]]; then
  echo "Query not found: $QUERY_FILE" >&2
  exit 1
fi

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

: "${POSTGRES_USER:=govbid}"
: "${POSTGRES_DB:=govbid}"

if docker compose ps postgres --status running -q 2>/dev/null | grep -q .; then
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/queries/${NAME}.sql"
elif command -v psql >/dev/null 2>&1; then
  : "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env for local psql}"
  export PGPASSWORD="$POSTGRES_PASSWORD"
  psql -h "${PGHOST:-localhost}" -p "${PGPORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f "$QUERY_FILE"
else
  echo "Start Postgres (docker compose up -d) or install psql." >&2
  exit 1
fi
