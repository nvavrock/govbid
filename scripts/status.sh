#!/usr/bin/env bash
# One-screen health check + top review opportunities (no Docker required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TOP_N="${1:-10}"

# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"
govbid_bootstrap_env "$ROOT"

echo "=== GovBid status ==="
echo ""

[[ -f .env ]] || { echo "FAIL Missing .env" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

if ! pg_isready -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" -q 2>/dev/null; then
  echo "Starting Postgres..."
  govbid_ensure_postgres "$ROOT"
fi

if pg_isready -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" -q; then
  echo "OK   Postgres (${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432})"
else
  echo "FAIL Postgres not reachable" >&2
  exit 1
fi

UV_BIN="$(govbid_resolve_uv)"
opp_count="$(
  export PGPASSWORD="${POSTGRES_PASSWORD:?}"
  psql -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" \
    -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" \
    -tAc "SELECT count(*) FROM opportunities;" 2>/dev/null | tr -d '[:space:]'
)"
if [[ "${opp_count:-0}" -gt 0 ]]; then
  echo "OK   ${opp_count} opportunities in database"
else
  echo "WARN 0 opportunities — run: ./run_ingest.sh"
fi

echo ""
echo "=== Top ${TOP_N} review opportunities ==="
"$UV_BIN" run scripts/review_queue.py 2>/dev/null | head -n $((TOP_N + 2))
