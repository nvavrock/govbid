#!/usr/bin/env bash
# Quick sanity check before cron or first run.
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$PROJECT/scripts/lib/common.sh"

failures=0

check() {
  local label="$1"
  shift
  if "$@"; then
    echo "OK   $label"
  else
    echo "FAIL $label" >&2
    failures=$((failures + 1))
  fi
}

check "project root exists" test -d "$PROJECT"
check "data directory" test -d "$PROJECT/data"
check "logs directory" test -d "$PROJECT/logs"
check "transcripts directory" test -d "$PROJECT/transcripts"
check "uv available" bash -c "source '$PROJECT/scripts/lib/common.sh' && govbid_resolve_uv >/dev/null"
check "python requests import" bash -c "cd '$PROJECT' && \"$(govbid_resolve_uv)\" run python -c 'import requests'"
check "download script syntax" python3 -m py_compile "$PROJECT/scripts/download_sam_opportunities.py"
check "run_download.sh syntax" bash -n "$PROJECT/run_download.sh"

if [[ -f "$PROJECT/pyproject.toml" ]]; then
  check "pyproject.toml present" test -f "$PROJECT/pyproject.toml"
fi

check "docker compose file" test -f "$PROJECT/docker-compose.yml"
check "postgres migrations" test -d "$PROJECT/db/migrations"
check "match profile example" test -f "$PROJECT/config/match-profile.example.yaml"
check "psycopg import" bash -c "cd '$PROJECT' && \"$(govbid_resolve_uv)\" run python -c 'import psycopg'"

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "OK   docker daemon running"
  else
    echo "WARN docker installed but daemon not running (needed for pipeline stack)" >&2
  fi
else
  echo "WARN docker not installed (needed for pipeline stack)" >&2
fi

if [[ $failures -gt 0 ]]; then
  echo "" >&2
  echo "$failures check(s) failed. Run: cd $PROJECT && uv sync" >&2
  exit 1
fi

echo ""
echo "All checks passed."
