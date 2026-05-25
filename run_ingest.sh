#!/usr/bin/env bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$PROJECT/scripts/lib/common.sh"

UV_BIN="$(govbid_resolve_uv)"
cd "$PROJECT"

echo "=== $(date -Is) starting SAM CSV ingest ==="
"$UV_BIN" run scripts/ingest_sam_csv.py
echo "=== $(date -Is) finished SAM CSV ingest ==="
