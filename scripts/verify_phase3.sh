#!/usr/bin/env bash
# Verify Phase 3: fit survey tables + RAG indexing smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0
warn() { echo "WARN $*"; }
fail() { echo "FAIL $*"; FAIL=1; }
ok() { echo "OK   $*"; }

echo "=== Phase 3 verification ==="

if ! bash "$ROOT/scripts/verify_phase2.sh" >/dev/null 2>&1; then
  fail "Phase 2 verification failed — fix Phase 2 first"
fi

source "$ROOT/scripts/lib/docker.sh" 2>/dev/null || true
if ! command -v docker >/dev/null 2>&1; then
  warn "docker not available — skipping Postgres checks"
else
  if command -v govbid_resolve_docker >/dev/null 2>&1 && govbid_resolve_docker >/dev/null 2>&1; then
    table_exists="$(govbid_docker_compose exec -T postgres psql -U "${POSTGRES_USER:-govbid}" -d "${POSTGRES_DB:-govbid}" -tAc \
      "SELECT to_regclass('public.consig_fit_surveys') IS NOT NULL;" 2>/dev/null || echo false)"
    if [[ "$table_exists" == "t" || "$table_exists" == "true" ]]; then
      ok "consig_fit_surveys table exists"
    else
      fail "consig_fit_surveys table missing — run: bash scripts/apply_fit_survey_migration.sh"
    fi
  else
    warn "Docker/Postgres not available — skipping table existence check"
  fi
fi

UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
  fail "uv not found"
else
  # Chroma presence smoke (no embeddings required)
  if "$UV_BIN" run python -c "from consig import rag; print(rag.collection_count())" >/dev/null 2>&1; then
    ok "Chroma collection_count() callable"
  else
    warn "Chroma collection_count() check failed"
  fi

  if "$UV_BIN" run scripts/index_fit_feedback.py --dry-run >/dev/null 2>&1; then
    ok "index_fit_feedback.py --dry-run"
  else
    fail "index_fit_feedback.py --dry-run failed"
  fi
  if "$UV_BIN" run scripts/smoke_fit_survey_roundtrip.py >/dev/null 2>&1; then
    ok "save_fit_survey round-trip"
  else
    fail "save_fit_survey round-trip failed"
  fi

  # Optional: embeddings index smoke (only if OPENAI_API_KEY is set)
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    if "$UV_BIN" run scripts/smoke_fit_survey_roundtrip.py --index >/dev/null 2>&1; then
      ok "Chroma indexing smoke (embeddings)"
    else
      warn "Embeddings indexing smoke failed — check OPENAI_API_KEY / embeddings"
    fi
  else
    warn "OPENAI_API_KEY not set — skipping embeddings indexing smoke"
  fi
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "Phase 3 verification PASSED"
  exit 0
fi
echo "Phase 3 verification FAILED"
exit 1

