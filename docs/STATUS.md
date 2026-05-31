# GovBid status

**Last updated:** 2026-05-31  
**Owner:** Rocksteady Analytics  

> Update this file when phase gates change, after merges to `main`, or weekly during ops checks.  
> Re-run verification: `bash scripts/doctor.sh` and `bash scripts/verify_phase1.sh` … `verify_phase3.sh`

## Current focus

Phase 1 runtime is **live**. Optional next steps: Phase 2 (`SLACK_WEBHOOK_URL`, digest) and Phase 3 (`OPENAI_API_KEY`, Consig RAG index).

## Phase gates

| Phase | Goal | Gate | Last verified | Result |
|-------|------|------|---------------|--------|
| 0 | Foundation (download, docs, corpus) | Manual | 2026-05-31 | **Done** |
| 1 | Filter, score, load to Postgres | `bash scripts/verify_phase1.sh` | 2026-05-31 | **Pass** — 4,793 opportunities; 25 pending review rows |
| 2 | Dashboard + digest | `bash scripts/verify_phase2.sh` | 2026-05-31 | **Fail** — `SLACK_WEBHOOK_URL` not set |
| 3 | Consig RAG + fit survey | `bash scripts/verify_phase3.sh` | 2026-05-31 | **Fail** — depends on Phase 2; `OPENAI_API_KEY` not set |
| 4 | Research + proposal agents | — | — | **Not started** |
| 5 | Live capture execution | — | — | **Ongoing** (business process) |

**Code vs runtime:** Phases 1–3 are **implemented on `main`**. Phase 1 verified locally; Phases 2–3 need optional API keys.

## What's done

- SAM bulk CSV download (`run_download.sh`) with daily cron at 6:00 AM
- Full repo on GitHub (`nvavrock/govbid`) — Consig, Postgres migrations, n8n workflows
- GovClose tooling removed; `transcripts/` gitignored (proprietary, local only)
- Docs: gameplan, consig-plan, SDLC, playbooks
- Latest local CSV: `data/ContractOpportunitiesFull_20260530.csv` (~229 MB)
- Local `.env` + `config/match-profile.yaml`; Docker stack up; ingest complete
- n8n 2.17+ owner auto-provisioned from `.env` (no manual `/setup` wizard)
- Daily pipeline cron: `run_daily.sh` at 6:00 AM (download + ingest + status)

## In progress

- Consig: Phase C/D polish per [consig-plan.md](consig-plan.md)

## Blocked / next

1. Optional: set `SLACK_WEBHOOK_URL` → `bash scripts/verify_phase2.sh`
2. Optional: set `OPENAI_API_KEY` → build Consig index → `bash scripts/verify_phase3.sh`
3. Consider consolidating duplicate 6 AM crons (`run_download.sh` + `run_daily.sh`; daily already downloads)

## Ops snapshot

| Item | Status |
|------|--------|
| Git branch | `main` (synced with `origin/main`) |
| SAM download cron | `0 6 * * * /home/me/govbid/run_download.sh` |
| Daily pipeline cron | `0 6 * * * cd /home/me/govbid && run_daily.sh` |
| Digest cron | `30 6 * * * run_digest.sh` (no-op until Slack webhook set) |
| `.env` | Present (gitignored) |
| `config/match-profile.yaml` | Present (gitignored) |
| Docker stack | Postgres :5433, n8n 2.17 :5678 (owner from `.env`), Adminer :8081, Consig :8000/:8501 |
| Last ingest | 2026-05-30 — success, 4,793 opportunities, 25 review queue rows |
| Training corpus | Local: `transcripts/corpus/combined.txt` (gitignored) |

## Related docs

- [gameplan.md](gameplan.md) — phased roadmap (what to build)
- [sdlc.md](sdlc.md) — how to build (verify before merge)
- [consig-plan.md](consig-plan.md) — Consig implementation detail
