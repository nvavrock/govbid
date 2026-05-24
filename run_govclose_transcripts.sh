#!/usr/bin/env bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT"

echo "=== $(date -Is) starting GovClose transcript fetch ==="

"$PROJECT/scripts/fetch_govclose_transcripts.sh" >> "$LOG_DIR/govclose_transcripts.log" 2>&1

echo "=== $(date -Is) finished GovClose transcript fetch ==="
