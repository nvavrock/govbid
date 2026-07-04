# Shared psql helpers — user-space Postgres, RDS, or optional Docker.
# Usage: ROOT=...; source "$ROOT/scripts/lib/postgres.sh"

_govbid_psql_common_loaded() { :; }

govbid_load_env() {
  [[ -n "${ROOT:-}" ]] || return 1
  [[ -f "$ROOT/.env" ]] || return 1
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
  return 0
}

govbid_psql_prepare() {
  local project="${1:-${ROOT:-}}"
  [[ -n "$project" ]] || {
    echo "govbid_psql_prepare: ROOT not set" >&2
    return 1
  }
  # shellcheck source=lib/common.sh
  source "$project/scripts/lib/common.sh"
  govbid_bootstrap_env "$project"
  govbid_load_env || {
    echo "Missing .env — cp .env.example .env" >&2
    return 1
  }

  export PGHOST="${POSTGRES_HOST:-127.0.0.1}"
  export PGPORT="${POSTGRES_PORT:-5432}"
  export PGUSER="${POSTGRES_USER:-govbid}"
  export PGDATABASE="${POSTGRES_DB:-govbid}"
  export PGPASSWORD="${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"

  if ! command -v psql >/dev/null 2>&1; then
    echo "psql not found — run: bash scripts/setup_user_postgres.sh" >&2
    return 1
  fi

  if ! pg_isready -h "$PGHOST" -p "$PGPORT" -q 2>/dev/null; then
    govbid_ensure_postgres "$project" || return 1
  fi

  pg_isready -h "$PGHOST" -p "$PGPORT" -q
}

govbid_psql() {
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 "$@"
}

govbid_psql_scalar() {
  govbid_psql -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}
