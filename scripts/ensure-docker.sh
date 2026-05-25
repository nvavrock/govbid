#!/usr/bin/env bash
# Verify Docker is usable in WSL (Docker Desktop must be running with WSL integration).
set -euo pipefail

DOCKER_CLI="/mnt/wsl/docker-desktop/cli-tools/usr/bin/docker"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Docker OK: $(docker compose version 2>/dev/null || docker --version)"
  exit 0
fi

echo "Docker is not available in this WSL session."
echo ""

if [[ ! -e "$DOCKER_CLI" ]]; then
  echo "Cause: Docker Desktop is not running, or WSL integration is not active yet."
  echo ""
  echo "Fix (in order):"
  echo "  1. Start Docker Desktop on Windows and wait until it says 'Running'"
  echo "  2. Docker Desktop → Settings → Resources → WSL integration"
  echo "     → Enable for your distro: Ubuntu"
  echo "  3. In PowerShell (Windows):  wsl --shutdown"
  echo "  4. Reopen this terminal, then run:  bash scripts/ensure-docker.sh"
  echo ""
  if command -v powershell.exe >/dev/null 2>&1; then
    echo "Attempting to start Docker Desktop..."
    powershell.exe -NoProfile -Command \
      "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe' -ErrorAction SilentlyContinue" || true
    echo "Wait ~30s for Docker to start, then run this script again."
  fi
  exit 1
fi

echo "Docker CLI exists but 'docker info' failed. Try: wsl --shutdown (from PowerShell), then reopen terminal."
exit 1
