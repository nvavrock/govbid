#!/usr/bin/env bash
# Verify Phase 1 deliverable: profile-driven review queue + recent successful ingest.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0
warn() { echo "WARN $*"; }
fail() { echo "FAIL $*"; FAIL=1; }
ok() { echo "OK   $*"; }

echo "=== Phase 1 verification ==="

if [[ ! -f config/match-profile.yaml ]]; then
  fail "config/match-profile.yaml missing — cp config/match-profile.example.yaml config/match-profile.yaml"
else
  ok "match-profile.yaml present"
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  fail "Missing .env"
fi

if [[ -n "${SAM_BULK_CSV_URL:-}" ]] || compgen -G "$ROOT/data/ContractOpportunitiesFull_*.csv" >/dev/null; then
  ok "SAM data source (URL or local CSV)"
else
  fail "No SAM_BULK_CSV_URL and no data/ContractOpportunitiesFull_*.csv"
fi

# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh" 2>/dev/null || true
if command -v docker >/dev/null 2>&1 && govbid_resolve_docker >/dev/null 2>&1; then
  opp_count="$(govbid_docker_compose exec -T postgres psql -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" -tAc \
    "SELECT count(*) FROM opportunities;" 2>/dev/null | tr -d '[:space:]' || echo 0)"
  if [[ "${opp_count:-0}" -gt 0 ]]; then
    ok "$opp_count opportunities in database"
  else
    fail "0 opportunities — run: ./run_daily.sh"
  fi

  ingest_status="$(govbid_docker_compose exec -T postgres psql -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" -tAc \
    "SELECT status FROM ingest_runs ORDER BY id DESC LIMIT 1;" 2>/dev/null | tr -d '[:space:]' || true)"
  if [[ "$ingest_status" == "success" ]]; then
    ok "last ingest_run: success"
    ingest_age_h="$(govbid_docker_compose exec -T postgres psql -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" -tAc \
      "SELECT EXTRACT(EPOCH FROM (NOW() - COALESCE(finished_at, started_at))) / 3600 FROM ingest_runs WHERE status = 'success' ORDER BY id DESC LIMIT 1;" 2>/dev/null | tr -d '[:space:]' || echo 999)"
    if [[ -n "$ingest_age_h" ]] && awk "BEGIN {exit !($ingest_age_h > 48)}" 2>/dev/null; then
      warn "last successful ingest older than 48h — run: ./run_daily.sh"
    fi
  else
    warn "last ingest_run not success ($ingest_status) — run: ./run_ingest.sh"
  fi
else
  warn "Docker/Postgres not available — run: bash scripts/doctor.sh"
fi

UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
  warn "uv not found — skipping review queue checks"
else
  queue_report="$("$UV_BIN" run scripts/verify_phase1_queue.py 2>&1)" || queue_report=""
  if [[ -z "$queue_report" ]]; then
    fail "review queue check failed (Python/DB error)"
  else
    # shellcheck disable=SC1090
    eval "$(echo "$queue_report" | grep -E '^[a-z_]+=')"
    if [[ "${qcount:-0}" -ge 1 ]]; then
      ok "review queue has ${qcount} pending row(s) (min_score=${min_score}, days_ahead=${days_ahead})"
    else
      fail "review queue empty — tune match-profile.yaml or run ./run_ingest.sh"
    fi
    if [[ "${qcount:-0}" -ge 1 && "${top_score_ok:-0}" != "1" ]]; then
      fail "top row rule_score below min_score (${top_score} < ${min_score})"
    fi
    if [[ "${qcount:-0}" -ge 1 && "${top_link_ok:-0}" != "1" ]]; then
      fail "top row missing valid ui_link"
    fi
    echo ""
    echo "=== Top queue titles ==="
    echo "$queue_report" | sed -n '/^--- sample ---$/,/^--- end ---$/p' | grep -v '^---'
  fi
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "Phase 1 verification PASSED"
  exit 0
fi
echo "Phase 1 verification FAILED"
exit 1
