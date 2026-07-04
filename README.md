# govbid

Federal contract opportunity system: SAM.gov bulk download, Postgres scoring pipeline, and **Counsel** — a capture advisor with best-fit ranking.

**Current status:** [docs/STATUS.md](docs/STATUS.md)  
**Product plan:** [docs/counsel-plan.md](docs/counsel-plan.md)  
**Community standards:** [docs/community-standards.md](docs/community-standards.md)

## Quick start (local, no Docker)

```bash
cd /home/me/govbid
uv sync
cp .env.example .env
cp config/match-profile.example.yaml config/match-profile.yaml
# Edit .env — POSTGRES_PASSWORD, optional OPENAI_API_KEY / SLACK_WEBHOOK_URL

bash scripts/setup_user_postgres.sh   # user-space Postgres on :5432
bash scripts/apply_migrations.sh
./run_daily.sh                        # download + ingest + status
./run_counsel.sh                      # dashboard http://127.0.0.1:8501
```

**Postgres ports:** user-space `.postgres/` → `5432` · Docker legacy → `5433` · AWS RDS → `5432`

## Project layout

```
govbid/
├── README.md
├── pyproject.toml
├── docker-compose.yml          # optional legacy stack
├── terraform/                  # optional AWS RDS
├── counsel/                    # FastAPI + Streamlit capture advisor
├── config/match-profile.yaml   # fit profile (gitignored; copy from .example)
├── db/migrations/              # Postgres schema
├── scripts/                    # ingest, status, verify, setup_user_postgres.sh
├── run_daily.sh                # cron: download → ingest → status
├── data/                       # SAM CSV (gitignored)
├── logs/                       # cron logs (gitignored)
└── docs/                       # STATUS, gameplan, community-standards, counsel-plan
```

## Daily use

```bash
./run_daily.sh              # download + ingest + status
./run_counsel.sh            # Counsel UI http://127.0.0.1:8501
./run_digest.sh             # Slack digest (needs SLACK_WEBHOOK_URL)
./scripts/status.sh 10      # health + top 10 best-fit rows
uv run scripts/review_queue.py
```

Install cron: `bash scripts/install_daily_cron.sh --install`

See [docs/dashboard.md](docs/dashboard.md) for queue tabs and shortlist workflow.

## Counsel

OpenAI RAG over playbooks and local training corpus (`transcripts/`, gitignored).

```bash
uv sync --extra counsel
uv run scripts/build_counsel_index.py
./run_counsel.sh
```

Plan and gaps vs open source: [docs/counsel-plan.md](docs/counsel-plan.md)

**My fit profile** tab edits `fit_profiles` in Postgres (NAICS, keywords, set-asides). Use **Refresh scores** after saving to re-rank opportunities. **Best fits** tab shows the ranked queue by fit band — no min-score slider.

## Matching

Edit criteria in the Counsel **My fit profile** tab, or in `config/match-profile.yaml` for CLI/cron — NAICS, keywords, set-asides, `ingest.mode` (`full` | `filtered`), and `review:` queue settings. YAML syncs to `fit_profiles` on ingest.

**Full ingest** loads all active SAM rows (~76k+); scoring ranks **best fit** with `fit_band` (strong / good / stretch) and `match_reasons` — not a hard pass/fail grade.

## Optional: Docker / AWS

| Path | When |
|------|------|
| [scripts/setup_user_postgres.sh](scripts/setup_user_postgres.sh) | **Default** local Postgres (no root) |
| [docker-compose.yml](docker-compose.yml) | Legacy n8n + Adminer + Counsel containers |
| [docs/aws-deploy.md](docs/aws-deploy.md) | Managed RDS + cloud compute |

## Verification

```bash
bash scripts/check_env.sh
bash scripts/verify_phase1.sh
bash scripts/verify_phase2.sh
bash scripts/verify_phase3.sh
```

Note: `scripts/doctor.sh` works without Docker (Postgres-first); Docker/n8n checks are optional.

## Local data (gitignored)

| Path | Purpose |
|------|---------|
| `.postgres/` | User-space PostgreSQL cluster |
| `data/*.csv` | SAM bulk extract (~200MB+) |
| `data/counsel_index/` | Chroma vector index |
| `transcripts/` | Proprietary RAG corpus |
| `logs/` | `daily.log`, `digest.log`, locks |
| `.env`, `config/match-profile.yaml` | Secrets and fit profile |

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/STATUS.md](docs/STATUS.md) | Living ops snapshot |
| [docs/counsel-plan.md](docs/counsel-plan.md) | Counsel product roadmap |
| [docs/community-standards.md](docs/community-standards.md) | Quality bar, anti-slop, AI-assisted work |
| [docs/gameplan.md](docs/gameplan.md) | Phased roadmap |
| [docs/sdlc.md](docs/sdlc.md) | Plan → verify → deploy |
| [docs/dashboard.md](docs/dashboard.md) | UI + digest |
| [docs/aws-deploy.md](docs/aws-deploy.md) | AWS target architecture |
| [docs/PAUSE_REPORT.md](docs/PAUSE_REPORT.md) | Historical pause notes (superseded) |

## Operations

- **Lock files** in `logs/` prevent overlapping cron runs.
- **Do not scrape SAM.gov** — official bulk extract and API only.
- Register at [sam.gov](https://sam.gov) for API keys when using n8n delta workflows.
- Contributions: read [docs/community-standards.md](docs/community-standards.md) before opening PRs.
