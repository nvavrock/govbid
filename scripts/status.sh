#!/usr/bin/env bash
# One-screen health check + top review opportunities.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TOP_N="${1:-10}"

echo "=== GovBid status ==="
echo ""

if ! bash "$ROOT/scripts/doctor.sh"; then
  exit 1
fi

echo ""
echo "=== Top ${TOP_N} review opportunities ==="
uv run scripts/review_queue.py 2>/dev/null | head -n $((TOP_N + 2)) || \
  bash scripts/run-query.sh review_queue 2>/dev/null | head -n $((TOP_N + 2))
