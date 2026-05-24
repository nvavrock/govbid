#!/usr/bin/env bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$PROJECT/scripts/lib/common.sh"

LOG_DIR="$PROJECT/logs"
LOCK_FILE="$LOG_DIR/govclose_transcripts.lock"

mkdir -p "$LOG_DIR"
cd "$PROJECT"

govbid_require_cmd yt-dlp "Install: sudo apt install -y yt-dlp"
govbid_acquire_lock "$LOCK_FILE" "GovClose transcript fetch"

echo "=== $(date -Is) starting GovClose transcript fetch ==="

if ! "$PROJECT/scripts/fetch_govclose_transcripts.sh" >>"$LOG_DIR/govclose_transcripts.log" 2>&1; then
  echo "=== $(date -Is) GovClose transcript fetch FAILED (see $LOG_DIR/govclose_transcripts.log) ===" >&2
  exit 1
fi

echo "=== $(date -Is) finished GovClose transcript fetch ==="
