#!/usr/bin/env bash
# Import GovBid Postgres credential and SAM workflows into local n8n.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/docker.sh
source "$ROOT/scripts/lib/docker.sh"
govbid_resolve_docker >/dev/null || {
  echo "Docker unavailable. Run: bash scripts/ensure-docker.sh" >&2
  exit 1
}

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${POSTGRES_USER:=govbid}"
: "${POSTGRES_DB:=govbid}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"

export POSTGRES_USER POSTGRES_DB POSTGRES_PASSWORD

if ! govbid_docker_compose ps --status running n8n 2>/dev/null | grep -q n8n; then
  echo "Starting stack..."
  govbid_docker_compose up -d
fi

bash "$ROOT/scripts/wait-n8n.sh" 45 || {
  echo "" >&2
  echo "n8n failed to start. If logs mention encryption keys, run:" >&2
  echo "  GOVBID_CONFIRM_RESET=yes bash scripts/reset-n8n-volume.sh" >&2
  exit 1
}

USER_ID="$(govbid_docker_compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT id FROM \"user\" WHERE email IS NOT NULL AND email <> '' LIMIT 1;")"
USER_ID="${USER_ID//[[:space:]]/}"

if [[ -z "$USER_ID" ]]; then
  echo "No n8n owner user found. Complete owner setup at http://localhost:5678 first." >&2
  exit 1
fi

CRED_FILE="$(mktemp)"
python3 - "$CRED_FILE" <<'PY'
import json, os, sys, uuid
path = sys.argv[1]
payload = [{
    "id": str(uuid.uuid4()),
    "name": "GovBid Postgres",
    "type": "postgres",
    "data": {
        "host": "postgres",
        "port": 5432,
        "database": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "ssl": "disable",
        "sshTunnel": False,
    },
}]
with open(path, "w") as f:
    json.dump(payload, f)
PY

govbid_docker_compose cp "$CRED_FILE" n8n:/tmp/govbid-postgres-credential.json
rm -f "$CRED_FILE"

echo "Importing Postgres credential..."
govbid_docker_compose exec -T n8n n8n import:credentials \
  --input=/tmp/govbid-postgres-credential.json \
  --userId="$USER_ID"

WF_COUNT="$(govbid_docker_compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM workflow_entity WHERE name LIKE '%SAM%' OR name LIKE '%Review%' OR name LIKE '%USAspending%';" \
  | tr -d '[:space:]')"

if [[ "${WF_COUNT:-0}" -ge 4 ]]; then
  echo "Workflows already imported ($WF_COUNT). Skipping workflow import."
else
  echo "Normalizing workflow JSON for n8n 1.90..."
  python3 "$ROOT/scripts/normalize_n8n_workflows.py"
  echo "Importing workflows..."
  if ! govbid_docker_compose exec -T n8n n8n import:workflow \
    --separate \
    --input=/workflows/n8n \
    --userId="$USER_ID"; then
    echo "Workflow import failed. Workflows may still be importable from the n8n UI." >&2
    echo "  Workflows → Import from file → workflows/n8n/" >&2
    exit 1
  fi
fi

echo ""
echo "Done. Open http://localhost:5678"
echo "  1. Open each workflow — map Postgres nodes to 'GovBid Postgres' if prompted"
echo "  2. Test-run '01 - SAM Bulk CSV Ingest', then activate workflows"
