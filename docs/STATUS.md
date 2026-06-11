# GovBid status

**Last updated:** 2026-06-10  
**Owner:** Rocksteady Analytics  

> Update this file when phase gates change, after merges to `main`, or weekly during ops checks.  
> Re-run verification: `bash scripts/doctor.sh` and `bash scripts/verify_phase1.sh` … `verify_phase3.sh`

## Current focus

**Paused (2026-06-10)** — GovBid is not a current priority. See **[PAUSE_REPORT.md](PAUSE_REPORT.md)** for what was done, blockers, and the resume checklist.

Infrastructure migration to AWS ([aws-deploy.md](aws-deploy.md)) is **incomplete** (Terraform RDS not applied; `doctor.sh` still Docker-dependent). Last successful ingest: 2026-06-10 (4,743 opportunities on legacy Postgres).

Phases 1–3 were **verified locally** on 2026-05-31 (Docker Postgres).

## Phase gates

| Phase | Goal | Gate | Last verified | Result |
|-------|------|------|---------------|--------|
| 0 | Foundation (download, docs, corpus) | Manual | 2026-05-31 | **Done** |
| 1 | Filter, score, load to Postgres | `bash scripts/verify_phase1.sh` | 2026-05-31 | **Pass** — 4,793 opportunities; 25 pending review rows |
| 2 | Dashboard + digest | `bash scripts/verify_phase2.sh` | 2026-05-31 | **Pass** — Consig UI; Slack digest sent; 2 shortlist rows |
| 3 | Consig RAG + fit survey | `bash scripts/verify_phase3.sh` | 2026-05-31 | **Pass** — fit survey tables; `OPENAI_API_KEY` optional for embedding smoke |
| 4 | Research + proposal agents | — | — | **Not started** |
| 5 | Live capture execution | — | — | **Ongoing** (business process) |

**Code vs runtime:** Phases 1–3 implemented and verified on `main`. Full RAG chat quality improves with `OPENAI_API_KEY` + `build_consig_index.py`.

## What's done

- SAM bulk CSV download; daily pipeline via `run_daily.sh` at 6:00 AM
- Slack digest via `run_digest.sh` at 6:30 AM (`SLACK_WEBHOOK_URL` configured)
- Full repo on GitHub (`nvavrock/govbid`) — Consig, Postgres migrations, n8n workflows
- Legacy vendor transcript tooling removed; `transcripts/` gitignored (proprietary, local only)
- Docs: gameplan, consig-plan, SDLC, playbooks
- Latest local CSV: `data/ContractOpportunitiesFull_20260530.csv` (~229 MB)
- Local `.env` + `config/match-profile.yaml`; Docker stack up; ingest complete
- n8n 2.17+ owner auto-provisioned from `.env` (no manual `/setup` wizard)
- Consig dashboard at http://localhost:8501; shortlist workflow exercised

## In progress

_(none — project paused; see [PAUSE_REPORT.md](PAUSE_REPORT.md))_

## Blocked / next (when resumed)

1. Fix Terraform free-tier + apply RDS — [PAUSE_REPORT.md](PAUSE_REPORT.md)
2. `psql` + `apply_migrations.sh` → point `.env` at RDS
3. RDS-aware `doctor.sh` / status (retire Docker dependency)
4. Optional: `OPENAI_API_KEY` → full RAG index; Consig Phase C/D per [consig-plan.md](consig-plan.md)

## Ops snapshot

| Item | Status |
|------|--------|
| Git branch | `main` (synced with `origin/main`) |
| Daily pipeline cron | `0 6 * * * cd /home/me/govbid && run_daily.sh` |
| Digest cron | `30 6 * * * run_digest.sh` (Slack webhook configured) |
| `.env` | Present (gitignored) |
| `config/match-profile.yaml` | Present (gitignored) |
| Docker stack (legacy) | Postgres :5433, n8n :5678 — **migrating to AWS RDS** |
| AWS RDS | Phase 1 — `terraform/` (**not applied** — see PAUSE_REPORT) |
| Project | **Paused** — not a current priority |
| Last ingest | 2026-05-30 — success, 4,793 opportunities, 25 review queue rows |
| Shortlist | 1 reviewing, 1 bid (as of Phase 2 verify) |
| Training corpus | Local: `transcripts/corpus/combined.txt` (gitignored) |

## Related docs

- [gameplan.md](gameplan.md) — phased roadmap (what to build)
- [sdlc.md](sdlc.md) — how to build (verify before merge)
- [consig-plan.md](consig-plan.md) — Consig implementation detail
