# govbid

Federal contract opportunity system: SAM.gov bulk download, Postgres scoring pipeline (n8n), GovClose training corpus, and agent-assisted capture planning.

## Project layout

```
govbid/
├── README.md
├── pyproject.toml              # Python deps (requests, psycopg); managed with uv
├── docker-compose.yml          # Postgres + n8n + Adminer
├── .env.example
├── run_download.sh             # daily SAM.gov CSV pull → data/
├── run_govclose_transcripts.sh # refresh GovClose transcript corpus
├── config/
│   └── match-profile.example.yaml
├── db/
│   ├── migrations/             # Postgres schema (auto on first Docker boot)
│   ├── queries/                # review_queue, sanity_counts, etc.
│   └── DATA_DICTIONARY.md
├── workflows/n8n/              # import into n8n
├── scrapers/states/            # phase 2 state portals
├── docs/                       # gameplan, playbooks, reference PDFs
├── scripts/                    # ingest, queries, n8n provision, check_env
├── data/                       # SAM bulk CSV (gitignored)
├── logs/
└── transcripts/govclose/       # RAG corpus (tracked in git)
```

## Setup

```bash
cd /home/me/rs
uv sync
cp .env.example .env
cp config/match-profile.example.yaml config/match-profile.yaml
# Edit .env — POSTGRES_PASSWORD, N8N_BASIC_AUTH_PASSWORD, N8N_ENCRYPTION_KEY, SAM_API_KEY
./scripts/check_env.sh
bash scripts/stack-up.sh
bash scripts/provision-n8n.sh
```

## Daily use

```bash
./run_daily.sh              # download + ingest + top 15 opportunities
./scripts/status.sh 10      # health check + top 10 only
uv run scripts/review_queue.py
```

### Start the pipeline stack

```bash
bash scripts/ensure-docker.sh   # WSL: run this first
bash scripts/stack-up.sh
bash scripts/provision-n8n.sh   # after first login at http://localhost:5678
```

| Service | URL |
|---------|-----|
| n8n | http://localhost:5678 |
| Adminer | http://localhost:8081 (server: `postgres`, port `5432` inside Docker network) |

Host Postgres port is **5433** (avoids conflict with local PostgreSQL on 5432). Set `POSTGRES_PORT=5433` in `.env` for Python/SQL CLIs.

**WSL / Docker Desktop:** If you see *"docker could not be found in this WSL 2 distro"*:

1. Start **Docker Desktop** on Windows (wait until Running)
2. **Settings → Resources → WSL integration** → enable **Ubuntu**
3. In PowerShell: `wsl --shutdown`, then reopen your terminal
4. Run `bash scripts/ensure-docker.sh` again

Scripts auto-fallback to `docker.exe` when the Linux shim is broken.

## SAM.gov daily download

Host cron (feeds `data/` for n8n bulk ingest):

```bash
/home/me/rs/run_download.sh
```

```cron
0 6 * * * /home/me/rs/run_download.sh
```

Or let n8n workflow `01-sam-bulk-ingest` download via `SAM_BULK_CSV_URL` in `.env`.

Manual:

```bash
uv run scripts/download_sam_opportunities.py --help
```

Load CSV into Postgres:

```bash
./run_ingest.sh
```

## Review queue

After `./run_ingest.sh` or n8n ingest:

```bash
bash scripts/run-query.sh review_queue
uv run scripts/review_queue.py
```

## n8n workflows

| File | Schedule | Purpose |
|------|----------|---------|
| `01-sam-bulk-ingest.json` | Daily 2:00 AM ET | Bulk CSV → Postgres |
| `02-sam-api-delta.json` | Daily 6:00 AM ET | SAM API delta by NAICS |
| `03-usaspending-enrichment.json` | Weekly | Award history |
| `04-review-digest.json` | Daily 7:00 AM ET | Top opportunities digest |

See [db/DATA_DICTIONARY.md](db/DATA_DICTIONARY.md) and [docs/gameplan.md](docs/gameplan.md).

## GovClose transcripts

```bash
/home/me/rs/run_govclose_transcripts.sh
```

Corpus for **Consig** RAG: `transcripts/govclose/govclose_all.txt`

## Matching

Edit `config/match-profile.yaml` (gitignored) — NAICS, PSC, keywords, set-asides. Keep in sync with `db/queries/review_queue.sql` and n8n Code nodes.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/gameplan.md](docs/gameplan.md) | Phased roadmap |
| [docs/federal_contracting_playbook.md](docs/federal_contracting_playbook.md) | Capture strategy |
| [docs/sam_gov_procurement_framework.md](docs/sam_gov_procurement_framework.md) | SAM.gov lifecycle |

## Operations

- **Lock files** in `logs/` prevent overlapping cron runs.
- **Do not scrape SAM.gov** — official bulk extract and API only.
- Register entity + API key at [sam.gov](https://sam.gov) for higher rate limits.
