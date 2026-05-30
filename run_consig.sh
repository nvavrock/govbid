#!/usr/bin/env bash
# Build index (if needed), apply migration, launch Streamlit Consig UI (in-process chat).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

UV_BIN="$(command -v uv || true)"
[[ -n "$UV_BIN" ]] || { echo "uv not found" >&2; exit 1; }

"$UV_BIN" sync --extra consig

if [[ ! -d data/consig_index ]] || [[ -z "$(ls -A data/consig_index 2>/dev/null)" ]]; then
  echo "Building Consig corpus index (first run)..."
  "$UV_BIN" run scripts/build_consig_index.py
fi

bash scripts/apply_consig_migration.sh 2>/dev/null || true

export CONSIG_INPROCESS=1
echo "Consig UI http://127.0.0.1:8501"
exec "$UV_BIN" run streamlit run consig/ui.py --server.port 8501 --server.address 127.0.0.1
