# govbid

Federal contract opportunity system: SAM.gov bulk download, Postgres scoring pipeline (n8n), and agent-assisted capture planning.

## Project layout

```
govbid/
├── README.md
├── pyproject.toml              # Python deps (requests, psycopg); managed with uv
├── docker-compose.yml          # Postgres + n8n + Adminer
├── .env.example
├── run_download.sh             # daily SAM.gov CSV pull → data/
├── config/
│   └── match-profile.example.yaml
├── db/
│   ├── migrations/             # Postgres schema (auto on first Docker boot)
│   ├── queries/                # review_queue, sanity_counts, etc.
│   └── DATA_DICTIONARY.md
├── workflows/n8n/              # import into n8n
├── scrapers/states/            # phase 2 state portals
├── docs/                       # gameplan, playbooks, reference PDFs
├── consig/                     # FastAPI + Streamlit capture copilot
├── scripts/                    # ingest, queries, n8n provision, build_consig_index
├── data/                       # SAM bulk CSV (gitignored)
├── logs/
└── transcripts/                # proprietary RAG corpus (gitignored, local only)
```

## Setup

```bash
cd /home/me/govbid
uv sync
cp .env.example .env
cp config/match-profile.example.yaml config/match-profile.yaml
# Edit .env — POSTGRES_PASSWORD, N8N_BASIC_AUTH_PASSWORD, N8N_ENCRYPTION_KEY, SAM_API_KEY
# n8n UI login uses your owner email (default nvavrock@gmail.com) + N8N_BASIC_AUTH_PASSWORD
./scripts/check_env.sh
bash scripts/stack-up.sh
bash scripts/provision-n8n.sh
```

## Daily use

```bash
./run_daily.sh              # download + ingest + status
./run_consig.sh             # Phase 2 dashboard + capture copilot (http://127.0.0.1:8501)
./run_digest.sh             # Slack review digest (needs SLACK_WEBHOOK_URL)
./scripts/status.sh 10      # health check + top 10 only
uv run scripts/review_queue.py
```

See [docs/dashboard.md](docs/dashboard.md) for queue tabs, shortlist workflow, and Adminer fallback.

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

## SAM.gov daily pipeline

**Canonical daily job** (download → ingest → status, uses `config/match-profile.yaml`):

```bash
./run_daily.sh
```

Install host cron (06:00 local time by default):

```bash
bash scripts/install_daily_cron.sh          # print crontab line
bash scripts/install_daily_cron.sh --install
```

Logs: `logs/daily.log`. `flock` in `run_daily.sh` / `run_download.sh` / `run_ingest.sh` prevents overlapping runs.

n8n workflow `01-sam-bulk-ingest` is optional backup for very large files; **Python ingest** (`./run_ingest.sh`) is primary.

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

## Consig (capture copilot)

OpenAI RAG over playbooks and local training corpus, wired to your **review queue** and pass/bid workflow.

**Setup:**

```bash
# Add to .env: OPENAI_API_KEY=sk-...
uv sync --extra consig
uv run scripts/build_consig_index.py    # first time: chunk + embed corpus
bash scripts/apply_consig_migration.sh  # once per existing Postgres volume
```

**Run locally:**

```bash
./run_consig.sh          # Streamlit UI http://127.0.0.1:8501 (in-process chat)
./run_consig_api.sh      # FastAPI http://127.0.0.1:8000 (for n8n / Docker UI)
uv run scripts/consig_feedback_report.py
```

**Docker:**

```bash
bash scripts/stack-up.sh   # includes consig-api :8000 and consig-ui :8501
```

| Service | URL |
|---------|-----|
| Consig UI | http://localhost:8501 |
| Consig API | http://localhost:8000/health |

Plan: [docs/consig-plan.md](docs/consig-plan.md) — branch `feature/consig`

Corpus for **Consig** RAG: `transcripts/corpus/combined.txt` (local, gitignored)

## Phase 1 complete

```bash
bash scripts/verify_phase1.sh   # exit 0 = Phase 1 done
```

Deliverable: up to 25 pending opportunities with `rule_score >= min_score` (default 25), deadlines within `days_ahead` (default 30), SAM.gov links in Postgres — all driven by `config/match-profile.yaml`.

## Phase 2 complete

```bash
bash scripts/verify_phase2.sh   # exit 0 = Phase 2 done (requires Phase 1)
```

Deliverable: Consig dashboard for browse/shortlist/picks; Slack digest via `run_digest.sh` or n8n workflow `04`.

## Matching

Edit `config/match-profile.yaml` (gitignored) — NAICS, PSC, keywords, set-asides, and `review:` (`min_score`, `days_ahead`, `top_n`). Used by `scripts/ingest_sam_csv.py`, scoring refresh, and `scripts/review_queue.py`. Adminer query `db/queries/review_queue.sql` is approximate defaults only.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/sdlc.md](docs/sdlc.md) | Lightweight SDLC (plan → verify → deploy) |
| [docs/gameplan.md](docs/gameplan.md) | Phased roadmap |
| [docs/federal_contracting_playbook.md](docs/federal_contracting_playbook.md) | Capture strategy |
| [docs/sam_gov_procurement_framework.md](docs/sam_gov_procurement_framework.md) | SAM.gov lifecycle |

## Operations

- **Lock files** in `logs/` prevent overlapping cron runs.
- **Do not scrape SAM.gov** — official bulk extract and API only.
- Register entity + API key at [sam.gov](https://sam.gov) for higher rate limits.
