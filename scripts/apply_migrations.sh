#!/usr/bin/env bash
# Apply all db/migrations/*.sql to Postgres (RDS or local psql).
# Usage: bash scripts/apply_migrations.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -f .env ]] || { echo "Missing .env — copy from .env.example" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

: "${POSTGRES_USER:=govbid}"
: "${POSTGRES_DB:=govbid}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"
: "${POSTGRES_HOST:=localhost}"
: "${POSTGRES_PORT:=5432}"

MAMBA_PSQL="$ROOT/.postgres/mamba/bin"
if ! command -v psql >/dev/null 2>&1 && [[ -x "$MAMBA_PSQL/psql" ]]; then
  export PATH="$MAMBA_PSQL:$PATH"
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "Install psql (postgresql-client) for RDS migrations." >&2
  exit 1
fi

export PGPASSWORD="$POSTGRES_PASSWORD"

for migration in "$ROOT"/db/migrations/*.sql; do
  [[ -f "$migration" ]] || continue
  echo "Applying $(basename "$migration") ..."
  psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -v ON_ERROR_STOP=1 -f "$migration"
done

echo "All migrations applied."
