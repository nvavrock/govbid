# GovBid status

**Last updated:** 2026-07-04  
**Owner:** Rocksteady Analytics  

> Update this file when phase gates change, after merges to `main`, or weekly during ops checks.

## Current focus

**Counsel** — Phase 1 done: **76,824** opportunities ingested; best-fit queue with `fit_band`. Next: **Phase 2 profile UI** ([counsel-plan.md](counsel-plan.md)).

## Phase gates

| Phase | Goal | Gate | Last verified | Result |
|-------|------|------|---------------|--------|
| 0 | Foundation (download, docs, corpus) | Manual | 2026-05-31 | **Done** (code) |
| 1 | Filter, score, load to Postgres | `bash scripts/verify_phase1.sh` | 2026-05-31 | **Pass** (historical) — re-verify after fresh DB |
| 2 | Dashboard + digest | `bash scripts/verify_phase2.sh` | 2026-05-31 | **Pass** (historical) — re-verify after fresh DB |
| 3 | Counsel RAG + fit survey | `bash scripts/verify_phase3.sh` | 2026-05-31 | **Pass** (historical) — re-verify after fresh DB |
| 4 | Research + proposal agents | — | — | **Not started** |
| 5 | Live capture execution | — | — | **Ongoing** (business process) |

## What's done (code & repo)

- SAM bulk CSV download (`run_download.sh`); Python ingest (`run_ingest.sh`)
- Postgres schema in `db/migrations/`; match profile in `config/match-profile.yaml`
- Counsel (FastAPI + Streamlit + Chroma RAG); Slack digest script
- Repo on GitHub (`nvavrock/govbid`); docs (gameplan, SDLC, counsel-plan)
- Legacy vendor transcript tooling removed; `transcripts/` gitignored (local only)

## In progress

1. **Fresh Postgres** — user-space install in `.postgres/` (no Docker, no sudo)

## Blocked / next

Do these in order:

1. ~~**Postgres + schema**~~ — done (2026-07-04): `setup_user_postgres.sh` + `apply_migrations.sh`
2. ~~**Smoke ingest**~~ — done (2026-07-04): 4,675 opportunities; review queue populated
3. ~~**Cron**~~ — fixed (2026-07-04): `PATH` in crontab; scripts bootstrap `uv` + Postgres
4. **Health scripts** — `doctor.sh` still Docker-only; use `scripts/status.sh` instead
5. **Later:** Counsel re-index, Slack digest, optional n8n or AWS ([aws-deploy.md](aws-deploy.md))

## Ops snapshot

| Item | Status |
|------|--------|
| Git branch | `main` |
| Postgres | **Up** — user-space on `127.0.0.1:5432` (`.postgres/`); run `bash scripts/setup_user_postgres.sh` after reboot |
| Docker / n8n | **Removed** — not in use |
| AWS RDS | Not applied (optional; see [PAUSE_REPORT.md](PAUSE_REPORT.md)) |
| Cron | **Active** — 6:00 daily, 6:30 digest (`PATH` includes `uv` + mamba `psql`) |
| `.env` | Present (gitignored) |
| `config/match-profile.yaml` | Present (gitignored) |
| Latest CSV on disk | `data/ContractOpportunitiesFull_20260704.csv` |
| Database rows | **76,824** active opportunities (full ingest 2026-07-04) |
| Training corpus | Local: `transcripts/corpus/combined.txt` (gitignored) |

## Related docs

- [gameplan.md](gameplan.md) — phased roadmap (what to build)
- [sdlc.md](sdlc.md) — how to build (verify before merge)
- [community-standards.md](community-standards.md) — quality bar and anti-slop policy
- [PAUSE_REPORT.md](PAUSE_REPORT.md) — June pause notes (partially superseded by fresh-start plan above)
