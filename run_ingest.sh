#!/usr/bin/env bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$PROJECT/scripts/lib/common.sh"
govbid_bootstrap_env "$PROJECT"

LOG_DIR="$PROJECT/logs"
LOCK_FILE="$LOG_DIR/ingest.lock"
mkdir -p "$LOG_DIR"
govbid_acquire_lock "$LOCK_FILE" "SAM ingest"

UV_BIN="$(govbid_resolve_uv)"
cd "$PROJECT"

echo "=== $(date -Is) starting SAM CSV ingest ==="
"$UV_BIN" run scripts/ingest_sam_csv.py
echo "=== $(date -Is) finished SAM CSV ingest ==="
