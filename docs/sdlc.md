# Lightweight SDLC for govbid

Solo workflow: **plan in docs → build on a branch → verify before merge → operate with cron/logs**.

Product milestones live in [gameplan.md](gameplan.md) (Phases 0–5). This doc maps classic SDLC stages to repo artifacts.

## Two “phase” systems

| Concept | Meaning |
|---------|---------|
| **SDLC stages** | How you build: plan → design → code → test → deploy → maintain |
| **Gameplan phases** | What the product delivers: ingest → dashboard → Counsel → agents → capture |

Run the SDLC loop for every change. Gameplan phases are milestones inside that loop.

## Stage mapping

| SDLC stage | govbid artifacts |
|------------|------------------|
| **Plan** | [gameplan.md](gameplan.md), [counsel-plan.md](counsel-plan.md), `config/match-profile.yaml` |
| **Design** | [db/migrations/](../db/migrations/), [DATA_DICTIONARY.md](../db/DATA_DICTIONARY.md), [workflows/n8n/](../workflows/n8n/), `docker-compose.yml` |
| **Build** | [scripts/](../scripts/), [counsel/](../counsel/), `pyproject.toml`, feature branches |
| **Test** | `scripts/check_env.sh`, `scripts/status.sh`, `scripts/doctor.sh`, `verify_phase1.sh` … `verify_phase3.sh` |
| **Deploy** | [aws-deploy.md](aws-deploy.md), `terraform/`, `./run_daily.sh`, cron; optional: `stack-up.sh` |
| **Operate** | `logs/`, `scripts/status.sh`, Counsel review loop, tune `match-profile.yaml` |

## Before merging to `main`

Read [community-standards.md](community-standards.md) (anti-slop, verify what you claim).

```bash
cd /home/me/govbid
bash scripts/check_env.sh
bash scripts/doctor.sh
bash scripts/verify_phase1.sh   # always
bash scripts/verify_phase2.sh   # if Counsel / dashboard changed
bash scripts/verify_phase3.sh   # if RAG / chat changed
```

Verification scripts are acceptance tests—no separate test suite required at this scale.

After verify passes, update [STATUS.md](STATUS.md) phase table and **Last updated** date.

## Git flow (solo)

- `main` — stable; passes verify for your current gameplan phase
- `feature/*` — one feature or fix per branch
- Small commits; merge when verify passes locally

## Release checklist (local deploy)

1. `bash scripts/status.sh` — Postgres up, opportunities loaded
2. `bash scripts/verify_phaseN.sh` — for current milestone
3. Cron: `bash scripts/install_daily_cron.sh --install` if needed
4. If corpus changed: `uv run scripts/build_counsel_index.py`
5. Legacy Docker/n8n: `bash scripts/doctor.sh`, `reset-n8n-login.sh` as needed

## Example: tighten NAICS filter

| Stage | Action |
|-------|--------|
| Plan | Note goal in gameplan or counsel-plan |
| Design | Edit `config/match-profile.yaml` |
| Build | `./run_ingest.sh` if ingest filters changed |
| Test | `bash scripts/verify_phase1.sh` |
| Deploy | Cron already runs daily pipeline |
| Operate | Watch queue 2–3 days; adjust keywords |

## Not needed (yet)

- GitHub Actions CI
- PR templates / review gates
- Separate staging environment

See [gameplan.md](gameplan.md) for phased roadmap and architecture.
