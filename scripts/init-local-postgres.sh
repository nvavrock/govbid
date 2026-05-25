#!/usr/bin/env bash
# Create govbid role/database and apply schema (local Postgres, e.g. via Docker or Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — run: cp .env.example .env" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

: "${POSTGRES_USER:=govbid}"
: "${POSTGRES_DB:=govbid}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"

ADMIN_USER="${PGADMIN_USER:-postgres}"
ADMIN_HOST="${PGADMIN_HOST:-localhost}"
ADMIN_PORT="${PGADMIN_PORT:-5432}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found. Install postgresql-client or use Docker:" >&2
  echo "  docker compose up -d" >&2
  exit 1
fi

sql_escape() {
  python3 -c "import sys; print(sys.argv[1].replace(\"'\", \"''\"))" "$1"
}

ESC_USER="$(sql_escape "$POSTGRES_USER")"
ESC_DB="$(sql_escape "$POSTGRES_DB")"
ESC_PASS="$(sql_escape "$POSTGRES_PASSWORD")"

echo "Creating role/database (connects as $ADMIN_USER)..."
read -rsp "Password for $ADMIN_USER: " ADMIN_PASS
echo
export PGPASSWORD="$ADMIN_PASS"

psql -h "$ADMIN_HOST" -p "$ADMIN_PORT" -U "$ADMIN_USER" -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${ESC_USER}') THEN
    CREATE ROLE ${ESC_USER} LOGIN PASSWORD '${ESC_PASS}';
  ELSE
    ALTER ROLE ${ESC_USER} WITH PASSWORD '${ESC_PASS}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${ESC_DB} OWNER ${ESC_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${ESC_DB}')\gexec
GRANT ALL PRIVILEGES ON DATABASE ${ESC_DB} TO ${ESC_USER};
SQL

unset PGPASSWORD
export PGPASSWORD="$POSTGRES_PASSWORD"
for migration in "$ROOT"/db/migrations/*.sql; do
  echo "Applying $(basename "$migration")..."
  psql -h "$ADMIN_HOST" -p "$ADMIN_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f "$migration"
done
unset PGPASSWORD

echo "Done. Database ${POSTGRES_DB} is ready."
