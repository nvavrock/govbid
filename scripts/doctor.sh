#!/usr/bin/env bash
# Health check: Postgres pipeline (primary) + optional legacy Docker/n8n stack.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/postgres.sh
source "$ROOT/scripts/lib/postgres.sh"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"
govbid_bootstrap_env "$ROOT"

FAIL=0
warn() { echo "WARN $*"; }
fail() { echo "FAIL $*"; FAIL=1; }
ok() { echo "OK   $*"; }

echo "=== GovBid doctor ==="
echo ""

if [[ ! -f .env ]]; then
  fail "Missing .env — run: cp .env.example .env"
  echo ""
  echo "Doctor FAILED (missing .env)"
  exit 1
fi

if bash "$ROOT/scripts/check_env.sh" >/dev/null 2>&1; then
  ok "check_env.sh passed"
else
  warn "check_env.sh reported issues — run: bash scripts/check_env.sh"
fi

if [[ -f config/match-profile.yaml ]]; then
  ok "match-profile.yaml present"
else
  warn "config/match-profile.yaml missing — cp config/match-profile.example.yaml config/match-profile.yaml"
fi

if govbid_psql_prepare "$ROOT"; then
  ok "Postgres (${PGHOST}:${PGPORT})"
  opp_count="$(govbid_psql_scalar "SELECT count(*) FROM opportunities;")"
  if [[ "${opp_count:-0}" -gt 0 ]]; then
    ok "$opp_count opportunities in database"
  else
    warn "0 opportunities — run: ./run_daily.sh"
  fi

  fit_count="$(govbid_psql_scalar \
    "SELECT count(*) FROM match_scores WHERE fit_band IN ('strong','good','stretch');")"
  if [[ "${fit_count:-0}" -gt 0 ]]; then
    ok "$fit_count opportunities with fit_band (strong/good/stretch)"
  else
    warn "no fit matches scored — check match-profile.yaml and run ./run_ingest.sh"
  fi

  ingest_status="$(govbid_psql_scalar "SELECT status FROM ingest_runs ORDER BY id DESC LIMIT 1;")"
  if [[ "$ingest_status" == "success" ]]; then
    ok "last ingest_run: success"
  else
    warn "last ingest_run: ${ingest_status:-none}"
  fi
else
  fail "Postgres not reachable — run: bash scripts/setup_user_postgres.sh"
fi

echo ""
echo "=== Optional legacy Docker stack ==="

# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh" 2>/dev/null || true
if govbid_resolve_docker >/dev/null 2>&1; then
  ok "Docker ($GOVBID_DOCKER)"
  govbid_docker_compose ps 2>/dev/null || true

  govbid_load_env 2>/dev/null || true
  bash "$ROOT/scripts/sync-postgres-password.sh" >/dev/null 2>&1 && \
    ok "Docker Postgres password synced" || true

  n8n_state="$(govbid_docker_compose ps n8n --format '{{.State}}' 2>/dev/null || echo missing)"
  if [[ "$n8n_state" == "running" ]]; then
    ok "n8n running — http://localhost:5678"
    N8N_VER="$(govbid_docker_compose exec -T n8n n8n --version 2>/dev/null | tr -d '[:space:]' || true)"
    [[ -n "$N8N_VER" ]] && ok "n8n version $N8N_VER"
  else
    warn "n8n not running (optional) — bash scripts/stack-up.sh"
  fi
else
  echo "INFO Docker not available — skipping n8n/Adminer checks (primary path: user-space Postgres)"
fi

echo ""
echo "=== Phase gates ==="

if bash "$ROOT/scripts/verify_phase1.sh" >/dev/null 2>&1; then
  echo "Phase 1: COMPLETE — best-fit review queue"
  echo "  Re-check: bash scripts/verify_phase1.sh"
else
  echo "Phase 1: incomplete"
  echo "  1. ./run_daily.sh"
  echo "  2. bash scripts/verify_phase1.sh"
fi

if bash "$ROOT/scripts/verify_phase2.sh" >/dev/null 2>&1; then
  echo "Phase 2: COMPLETE — Counsel dashboard + digest script"
  echo "  UI: ./run_counsel.sh  |  Digest: ./run_digest.sh"
else
  echo "Phase 2: incomplete"
  echo "  1. uv sync --extra counsel && ./run_counsel.sh"
  echo "  2. bash scripts/verify_phase2.sh"
fi

if bash "$ROOT/scripts/verify_phase3.sh" >/dev/null 2>&1; then
  echo "Phase 3: COMPLETE — fit survey + RAG feedback loop"
else
  echo "Phase 3: incomplete"
  echo "  1. bash scripts/apply_migrations.sh"
  echo "  2. uv run scripts/build_counsel_index.py"
  echo "  3. bash scripts/verify_phase3.sh"
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "Doctor PASSED (core pipeline healthy)"
  exit 0
fi
echo "Doctor FAILED (fix Postgres / .env first)"
exit 1
