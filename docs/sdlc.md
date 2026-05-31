# Lightweight SDLC for govbid

Solo workflow: **plan in docs → build on a branch → verify before merge → operate with cron/logs**.

Product milestones live in [gameplan.md](gameplan.md) (Phases 0–5). This doc maps classic SDLC stages to repo artifacts.

## Two “phase” systems

| Concept | Meaning |
|---------|---------|
| **SDLC stages** | How you build: plan → design → code → test → deploy → maintain |
| **Gameplan phases** | What the product delivers: ingest → dashboard → Consig → agents → capture |

Run the SDLC loop for every change. Gameplan phases are milestones inside that loop.

## Stage mapping

| SDLC stage | govbid artifacts |
|------------|------------------|
| **Plan** | [gameplan.md](gameplan.md), [consig-plan.md](consig-plan.md), `config/match-profile.yaml` |
| **Design** | [db/migrations/](../db/migrations/), [DATA_DICTIONARY.md](../db/DATA_DICTIONARY.md), [workflows/n8n/](../workflows/n8n/), `docker-compose.yml` |
| **Build** | [scripts/](../scripts/), [consig/](../consig/), `pyproject.toml`, feature branches |
| **Test** | `scripts/check_env.sh`, `doctor.sh`, `verify_phase1.sh` … `verify_phase3.sh` |
| **Deploy** | `scripts/stack-up.sh`, `./run_daily.sh`, cron via `scripts/install_daily_cron.sh` |
| **Operate** | `logs/`, `scripts/status.sh`, Consig review loop, tune `match-profile.yaml` |

## Before merging to `main`

```bash
cd /home/me/govbid
bash scripts/doctor.sh
bash scripts/verify_phase1.sh   # always
bash scripts/verify_phase2.sh   # if Consig / dashboard changed
bash scripts/verify_phase3.sh   # if RAG / chat changed
```

Verification scripts are acceptance tests—no separate test suite required at this scale.

After verify passes, update [STATUS.md](STATUS.md) phase table and **Last updated** date.

## Git flow (solo)

- `main` — stable; passes verify for your current gameplan phase
- `feature/*` — one feature or fix per branch
- Small commits; merge when verify passes locally

## Release checklist (local deploy)

1. `bash scripts/doctor.sh` — clean
2. `bash scripts/verify_phaseN.sh` — for current milestone
3. Cron for SAM download / daily ingest (see [README.md](../README.md))
4. If corpus changed: `uv run scripts/build_consig_index.py`

## Example: tighten NAICS filter

| Stage | Action |
|-------|--------|
| Plan | Note goal in gameplan or consig-plan |
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
