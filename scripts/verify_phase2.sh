#!/usr/bin/env bash
# Verify Phase 2: dashboard UI, review actions, Slack digest script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/postgres.sh
source "$ROOT/scripts/lib/postgres.sh"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

FAIL=0
warn() { echo "WARN $*"; }
fail() { echo "FAIL $*"; FAIL=1; }
ok() { echo "OK   $*"; }

echo "=== Phase 2 verification ==="

if ! bash "$ROOT/scripts/verify_phase1.sh" >/dev/null 2>&1; then
  fail "Phase 1 verification failed — fix Phase 1 first"
else
  ok "Phase 1 checks passed"
fi

govbid_load_env 2>/dev/null || true

UV_BIN="$(govbid_resolve_uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
  fail "uv not found"
else
  if "$UV_BIN" run python -c "import streamlit; import counsel.ui" 2>/dev/null; then
    ok "Counsel UI module loads (streamlit)"
  else
    fail "Counsel UI import failed — run: uv sync --extra counsel"
  fi

  if "$UV_BIN" run python -c "from counsel import db; assert db.list_fit_profiles()" 2>/dev/null; then
    ok "fit_profiles CRUD (list)"
  else
    fail "fit_profiles empty or DB error — run ./run_ingest.sh"
  fi

  if "$UV_BIN" run scripts/send_review_digest.py --dry-run >/dev/null 2>&1; then
    ok "send_review_digest.py --dry-run"
  else
    fail "send_review_digest.py --dry-run failed"
  fi
fi

if govbid_psql_prepare "$ROOT" 2>/dev/null; then
  shortlist_count="$(govbid_psql_scalar \
    "SELECT COUNT(*) FROM match_scores WHERE review_status IN ('reviewing', 'bid');")"
  if [[ "${shortlist_count:-0}" -ge 1 ]]; then
    ok "shortlist has ${shortlist_count} row(s) (reviewing/bid)"
  else
    warn "no reviewing/bid rows yet — use Counsel UI Shortlist/Bid buttons"
  fi
else
  warn "Postgres not available — skipped shortlist DB check"
fi

if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
  ok "SLACK_WEBHOOK_URL is set"
else
  warn "SLACK_WEBHOOK_URL not set — digest --send will fail until configured"
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "Phase 2 verification PASSED"
  exit 0
fi
echo "Phase 2 verification FAILED"
exit 1
