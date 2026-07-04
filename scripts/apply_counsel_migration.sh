#!/usr/bin/env bash
# Apply Counsel-related migrations via psql (no Docker).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/apply_migrations.sh"
