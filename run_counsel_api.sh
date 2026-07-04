#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

UV_BIN="$(command -v uv || true)"
[[ -n "$UV_BIN" ]] || { echo "uv not found" >&2; exit 1; }

"$UV_BIN" sync --extra counsel
echo "Counsel API http://127.0.0.1:8000"
exec "$UV_BIN" run uvicorn counsel.main:app --host 127.0.0.1 --port 8000 --reload
