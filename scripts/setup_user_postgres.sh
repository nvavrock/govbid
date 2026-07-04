#!/usr/bin/env bash
# User-space PostgreSQL 16 (no root). Uses micromamba; data in .postgres/data.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PG_HOME="$ROOT/.postgres"
PGDATA="$PG_HOME/data"
MAMBA_ROOT="$PG_HOME/mamba"
PGPORT="${GOVBID_PGPORT:-5432}"
MICROMAMBA="$ROOT/bin/micromamba"

[[ -f .env ]] || { echo "Missing .env" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a
: "${POSTGRES_USER:=govbid}"
: "${POSTGRES_DB:=govbid}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"

if [[ ! -x "$MAMBA_ROOT/bin/initdb" ]]; then
  echo "Installing PostgreSQL 16 via micromamba..."
  [[ -x "$MICROMAMBA" ]] || {
    mkdir -p "$ROOT/bin"
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C "$ROOT/bin" bin/micromamba
    mv "$ROOT/bin/bin/micromamba" "$MICROMAMBA" 2>/dev/null || true
    rmdir "$ROOT/bin/bin" 2>/dev/null || true
  }
  "$MICROMAMBA" install -y -r "$MAMBA_ROOT" -n base -c conda-forge postgresql=16
fi

export PATH="$MAMBA_ROOT/bin:$PATH"

if [[ ! -d "$PGDATA" ]]; then
  echo "Initializing database cluster..."
  initdb -D "$PGDATA" -U postgres --auth-local=trust --auth-host=scram-sha-256
  cat >> "$PGDATA/postgresql.conf" <<EOF

# govbid user-space
listen_addresses = 'localhost'
port = $PGPORT
EOF
  echo "host all all 127.0.0.1/32 scram-sha-256" >> "$PGDATA/pg_hba.conf"
  echo "host all all ::1/128 scram-sha-256" >> "$PGDATA/pg_hba.conf"
fi

if ! pg_isready -h 127.0.0.1 -p "$PGPORT" -q 2>/dev/null; then
  echo "Starting PostgreSQL on port $PGPORT..."
  pg_ctl -D "$PGDATA" -l "$PG_HOME/postgres.log" -o "-p $PGPORT" start
  for _ in $(seq 1 30); do
    pg_isready -h 127.0.0.1 -p "$PGPORT" -q && break
    sleep 1
  done
fi

pg_isready -h 127.0.0.1 -p "$PGPORT" -q || {
  echo "Postgres failed to start. See $PG_HOME/postgres.log" >&2
  exit 1
}

sql_escape() {
  python3 -c "import sys; print(sys.argv[1].replace(\"'\", \"''\"))" "$1"
}
ESC_USER="$(sql_escape "$POSTGRES_USER")"
ESC_DB="$(sql_escape "$POSTGRES_DB")"
ESC_PASS="$(sql_escape "$POSTGRES_PASSWORD")"

psql -U postgres -d postgres -v ON_ERROR_STOP=1 <<SQL
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

echo "PostgreSQL ready at 127.0.0.1:$PGPORT (user=$POSTGRES_USER db=$POSTGRES_DB)"
