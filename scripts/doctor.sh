#!/usr/bin/env bash
# Diagnose and repair common govbid stack issues (WSL Docker, ports, n8n, Postgres).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"

echo "=== GovBid doctor ==="

if ! govbid_resolve_docker >/dev/null; then
  echo "FAIL: Docker not available. Run: bash scripts/ensure-docker.sh"
  exit 1
fi
echo "OK   Docker ($GOVBID_DOCKER)"

if [[ ! -f .env ]]; then
  echo "FAIL: Missing .env — run: cp .env.example .env"
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ "${POSTGRES_PORT:-5432}" == "5432" ]]; then
  echo "WARN POSTGRES_PORT=5432 — host mapping is 5433; set POSTGRES_PORT=5433 in .env"
fi

if [[ "${N8N_ENCRYPTION_KEY:-}" == *change_me* ]]; then
  echo "WARN N8N_ENCRYPTION_KEY still placeholder — generate with: openssl rand -hex 16"
fi

govbid_docker_compose ps 2>/dev/null || true

bash "$ROOT/scripts/sync-postgres-password.sh" >/dev/null 2>&1 && echo "OK   Postgres password synced to .env" || true

N8N_VER="$(govbid_docker_compose exec -T n8n n8n --version 2>/dev/null | tr -d '[:space:]' || true)"
if [[ -n "$N8N_VER" ]]; then
  echo "OK   n8n version $N8N_VER"
fi

if govbid_docker_compose ps n8n --status running -q 2>/dev/null | grep -q .; then
  cfg_key="$(govbid_docker_compose exec -T n8n cat /home/node/.n8n/config 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('encryptionKey',''))" 2>/dev/null || true)"
  if [[ -n "$cfg_key" && "$cfg_key" != "${N8N_ENCRYPTION_KEY:-}" ]]; then
    echo "FAIL n8n encryption key mismatch (config vs .env)"
    echo "     Fix: GOVBID_CONFIRM_RESET=yes bash scripts/reset-n8n-volume.sh"
    exit 1
  fi
fi

n8n_state="$(govbid_docker_compose ps n8n --format '{{.State}}' 2>/dev/null || echo missing)"
if [[ "$n8n_state" != "running" ]]; then
  if govbid_docker_compose logs n8n --tail 5 2>/dev/null | grep -q "encryption keys"; then
    echo "FAIL n8n encryption key mismatch"
    echo "     Fix: GOVBID_CONFIRM_RESET=yes bash scripts/reset-n8n-volume.sh"
  else
    echo "FAIL n8n state: $n8n_state"
    echo "     Logs: govbid_docker_compose logs n8n --tail 20"
  fi
  exit 1
fi
echo "OK   n8n running — http://localhost:5678"
OWNER_EMAIL="${N8N_OWNER_EMAIL:-nvavrock@gmail.com}"
if [[ -n "${N8N_BASIC_AUTH_PASSWORD:-}" ]]; then
  if curl -sf -X POST http://127.0.0.1:5678/rest/login \
    -H 'Content-Type: application/json' \
    -d "{\"emailOrLdapLoginId\":\"$OWNER_EMAIL\",\"password\":\"$N8N_BASIC_AUTH_PASSWORD\"}" \
    | grep -q '"email"'; then
    echo "OK   n8n login for $OWNER_EMAIL (password = N8N_BASIC_AUTH_PASSWORD in .env)"
  else
    echo "WARN n8n login failed — run: bash scripts/reset-n8n-login.sh"
  fi
fi

opp_count="$(govbid_docker_compose exec -T postgres psql -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" -tAc \
  "SELECT count(*) FROM opportunities;" 2>/dev/null | tr -d '[:space:]' || echo 0)"
if [[ "${opp_count:-0}" -eq 0 ]]; then
  echo "WARN 0 opportunities in database — run: ./run_ingest.sh (after ./run_download.sh)"
else
  echo "OK   $opp_count opportunities in database"
fi

echo ""
if bash "$ROOT/scripts/verify_phase1.sh" >/dev/null 2>&1; then
  echo "Phase 1: COMPLETE — review queue meets match-profile.yaml criteria"
  echo "  Re-check: bash scripts/verify_phase1.sh"
else
  echo "Phase 1: incomplete"
  echo "  1. cp config/match-profile.example.yaml config/match-profile.yaml  (if missing)"
  echo "  2. ./run_daily.sh          (download + ingest + status)"
  echo "  3. bash scripts/verify_phase1.sh"
  echo "  4. uv run scripts/review_queue.py"
fi

if bash "$ROOT/scripts/verify_phase2.sh" >/dev/null 2>&1; then
  echo "Phase 2: COMPLETE — Consig dashboard + digest script ready"
  echo "  Daily UI: ./run_consig.sh  |  Digest: ./run_digest.sh"
else
  echo "Phase 2: incomplete"
  echo "  1. ./run_consig.sh           (opportunity dashboard)"
  echo "  2. Set SLACK_WEBHOOK_URL in .env (for Slack digest)"
  echo "  3. bash scripts/verify_phase2.sh"
  echo "  See: docs/dashboard.md"
fi

echo ""
if bash "$ROOT/scripts/verify_phase3.sh" >/dev/null 2>&1; then
  echo "Phase 3: COMPLETE — fit survey + RAG feedback loop"
  echo "  Daily habit: fill Fit survey after Pass/Bid in Consig."
else
  echo "Phase 3: incomplete"
  echo "  1. bash scripts/apply_fit_survey_migration.sh"
  echo "  2. uv run scripts/build_consig_index.py   (corpus)"
  echo "  3. uv run scripts/index_fit_feedback.py --dry-run"
  echo "  4. bash scripts/verify_phase3.sh"
  echo "  See: docs/gameplan.md (Phase 3) and docs/consig-plan.md"
fi
