#!/usr/bin/env bash
# Send review queue digest to Slack (after daily ingest).
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$PROJECT/scripts/lib/common.sh"

UV_BIN="$(govbid_resolve_uv)"
cd "$PROJECT"

"$UV_BIN" run scripts/send_review_digest.py --send
