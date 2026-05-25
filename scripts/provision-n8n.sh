#!/usr/bin/env bash
# Import GovBid Postgres credential and SAM workflows into local n8n.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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

if ! docker compose ps --status running n8n 2>/dev/null | grep -q n8n; then
  echo "Starting stack..."
  docker compose up -d
fi

USER_ID="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
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

docker compose cp "$CRED_FILE" n8n:/tmp/govbid-postgres-credential.json
rm -f "$CRED_FILE"

echo "Importing Postgres credential..."
docker compose exec -T n8n n8n import:credentials \
  --input=/tmp/govbid-postgres-credential.json \
  --userId="$USER_ID"

echo "Importing workflows..."
docker compose exec -T n8n n8n import:workflow \
  --separate \
  --input=/workflows/n8n \
  --userId="$USER_ID"

echo ""
echo "Done. Open http://localhost:5678"
echo "  1. Open each workflow — map Postgres nodes to 'GovBid Postgres' if prompted"
echo "  2. Test-run '01 - SAM Bulk CSV Ingest', then activate workflows"
