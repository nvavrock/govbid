#!/usr/bin/env bash
# Print or install crontab entry for ./run_daily.sh (download + ingest + status).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL=false
CRON_SCHEDULE="${GOVBID_DAILY_CRON:-0 6 * * *}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=true; shift ;;
    --schedule)
      CRON_SCHEDULE="${2:?}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: bash scripts/install_daily_cron.sh [--install] [--schedule '0 6 * * *']"
      echo "  Default schedule: 06:00 daily (host local time). Override with GOVBID_DAILY_CRON."
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

DIGEST_SCHEDULE="${GOVBID_DIGEST_CRON:-30 6 * * *}"
CRON_PATH="PATH=$HOME/.local/bin:$ROOT/.postgres/mamba/bin:/usr/local/bin:/usr/bin:/bin"
CRON_LINE="$CRON_SCHEDULE cd $ROOT && $ROOT/run_daily.sh >> $ROOT/logs/daily.log 2>&1"
DIGEST_LINE="$DIGEST_SCHEDULE cd $ROOT && $ROOT/run_digest.sh >> $ROOT/logs/digest.log 2>&1"

echo "=== GovBid daily cron ==="
echo ""
echo "Canonical daily job (download + ingest + status):"
echo "  $ROOT/run_daily.sh"
echo ""
echo "Crontab PATH (uv + psql for cron):"
echo "  $CRON_PATH"
echo ""
echo "Crontab line (ingest):"
echo "  $CRON_LINE"
echo ""
echo "Optional Slack digest (after ingest):"
echo "  $DIGEST_LINE"
echo ""

if [[ "$INSTALL" != true ]]; then
  echo "To install:"
  echo "  bash scripts/install_daily_cron.sh --install"
  echo ""
  echo "Or paste into crontab -e:"
  echo "  $CRON_PATH"
  echo "  $CRON_LINE"
  exit 0
fi

mkdir -p "$ROOT/logs"
touch "$ROOT/logs/daily.log"

( crontab -l 2>/dev/null \
  | grep -vF "$ROOT/run_daily.sh" \
  | grep -vF "$ROOT/run_digest.sh" \
  | grep -vF "$ROOT/run_download.sh" \
  | grep -vF "$ROOT/.postgres/mamba/bin" \
  || true
  echo "$CRON_PATH"
  echo "$CRON_LINE"
  echo "$DIGEST_LINE"
) | crontab -

echo "Installed. Current crontab:"
crontab -l | grep -E "run_daily|govbid" || crontab -l
