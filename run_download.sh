#!/usr/bin/env bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$PROJECT/scripts/lib/common.sh"
govbid_bootstrap_env "$PROJECT"

LOG_DIR="$PROJECT/logs"
LOCK_FILE="$LOG_DIR/download.lock"

mkdir -p "$LOG_DIR" "$PROJECT/data"
cd "$PROJECT"

UV_BIN="$(govbid_resolve_uv)"
govbid_acquire_lock "$LOCK_FILE" "SAM download"

echo "=== $(date -Is) starting SAM download ==="

if ! "$UV_BIN" run scripts/download_sam_opportunities.py >>"$LOG_DIR/download.log" 2>&1; then
  echo "=== $(date -Is) SAM download FAILED (see $LOG_DIR/download.log) ===" >&2
  exit 1
fi

echo "=== $(date -Is) finished SAM download ==="
