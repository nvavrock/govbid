#!/usr/bin/env bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV="${UV:-/home/me/.local/bin/uv}"
LOG_DIR="$PROJECT/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT"

echo "=== $(date -Is) starting SAM download ==="

"$UV" run scripts/download_sam_opportunities.py >> "$LOG_DIR/download.log" 2>&1

echo "=== $(date -Is) finished SAM download ==="
