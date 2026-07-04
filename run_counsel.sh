#!/usr/bin/env bash
# Build index (if needed), apply migration, launch Streamlit Counsel UI (in-process chat).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

UV_BIN="$(command -v uv || true)"
[[ -n "$UV_BIN" ]] || { echo "uv not found" >&2; exit 1; }

"$UV_BIN" sync --extra counsel

if [[ ! -d data/counsel_index ]] || [[ -z "$(ls -A data/counsel_index 2>/dev/null)" ]]; then
  echo "Building Counsel corpus index (first run)..."
  "$UV_BIN" run scripts/build_counsel_index.py
fi

bash scripts/apply_counsel_migration.sh 2>/dev/null || true

# Stop a previous Counsel/Streamlit instance on this port (common when re-running).
if command -v ss >/dev/null 2>&1; then
  old_pid="$(ss -tlnp 2>/dev/null | grep '127.0.0.1:8501' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2 || true)"
  if [[ -n "${old_pid:-}" ]]; then
    echo "Stopping previous Streamlit on port 8501 (pid $old_pid)..."
    kill "$old_pid" 2>/dev/null || true
    sleep 1
  fi
fi

export COUNSEL_INPROCESS=1
echo "Counsel UI http://127.0.0.1:8501"
exec "$UV_BIN" run streamlit run counsel/ui.py --server.port 8501 --server.address 127.0.0.1
