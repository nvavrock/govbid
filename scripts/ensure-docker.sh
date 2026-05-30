#!/usr/bin/env bash
# Verify Docker is usable in WSL (Docker Desktop must be running with WSL integration).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"

if govbid_resolve_docker >/dev/null; then
  echo "Docker OK: $(govbid_docker_compose version 2>/dev/null || govbid_docker --version)"
  echo "Using: $GOVBID_DOCKER"
  exit 0
fi

echo "Docker is not available in this WSL session."
echo ""

if command -v docker >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
  echo "Detected: 'docker' is on PATH but WSL integration is not active."
  echo "The Windows shim fails until Docker Desktop enables this distro."
  echo ""
fi

echo "Fix (in order):"
echo "  1. Start Docker Desktop on Windows and wait until it says 'Running'"
echo "  2. Docker Desktop → Settings → Resources → WSL integration"
echo "     → Enable for: Ubuntu (or your distro: ${WSL_DISTRO_NAME:-unknown})"
echo "  3. In PowerShell (Windows):  wsl --shutdown"
echo "  4. Reopen this terminal, then run:  bash scripts/ensure-docker.sh"
echo ""

if command -v powershell.exe >/dev/null 2>&1; then
  echo "Attempting to start Docker Desktop..."
  powershell.exe -NoProfile -Command \
    "Start-Process 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe' -ErrorAction SilentlyContinue" || true
  echo "Wait ~30s, enable WSL integration, wsl --shutdown, reopen terminal."
fi

exit 1
