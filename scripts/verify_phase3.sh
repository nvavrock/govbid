#!/usr/bin/env bash
# Verify Phase 3: fit survey tables + RAG indexing smoke.
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

echo "=== Phase 3 verification ==="

if ! bash "$ROOT/scripts/verify_phase2.sh" >/dev/null 2>&1; then
  fail "Phase 2 verification failed — fix Phase 2 first"
else
  ok "Phase 2 checks passed"
fi

if govbid_psql_prepare "$ROOT" 2>/dev/null; then
  table_exists="$(govbid_psql_scalar \
    "SELECT to_regclass('public.counsel_fit_surveys') IS NOT NULL;")"
  if [[ "$table_exists" == "t" || "$table_exists" == "true" ]]; then
    ok "counsel_fit_surveys table exists"
  else
    fail "counsel_fit_surveys table missing — run: bash scripts/apply_migrations.sh"
  fi
else
  fail "Postgres not reachable — run: bash scripts/setup_user_postgres.sh"
fi

govbid_load_env 2>/dev/null || true

UV_BIN="$(govbid_resolve_uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
  fail "uv not found"
else
  if "$UV_BIN" run python -c "from counsel import rag; print(rag.collection_count())" >/dev/null 2>&1; then
    ok "Chroma collection_count() callable"
  else
    warn "Chroma collection_count() check failed — run: uv run scripts/build_counsel_index.py"
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

  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    if "$UV_BIN" run scripts/smoke_fit_survey_roundtrip.py --index >/dev/null 2>&1; then
      ok "Chroma indexing smoke (embeddings)"
    else
      warn "Embeddings indexing smoke failed — check OPENAI_API_KEY"
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
