#!/usr/bin/env bash
# Daily pipeline: download SAM CSV → ingest → show status.
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT"
# shellcheck source=scripts/lib/common.sh
source "$PROJECT/scripts/lib/common.sh"

LOG_DIR="$PROJECT/logs"
LOCK_FILE="$LOG_DIR/daily.lock"
mkdir -p "$LOG_DIR"
govbid_acquire_lock "$LOCK_FILE" "run_daily"

echo "Step 1/3: Download SAM bulk CSV"
"$PROJECT/run_download.sh"

echo ""
echo "Step 2/3: Ingest into Postgres"
"$PROJECT/run_ingest.sh"

echo ""
echo "Step 3/3: Status"
"$PROJECT/scripts/status.sh" 15
