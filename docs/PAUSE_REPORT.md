# GovBid — pause report (2026-06-10)

> **Superseded for ops (2026-07-04):** See **[STATUS.md](STATUS.md)** — user-space Postgres, full SAM ingest, active cron. This file is historical context for the AWS migration pause only.

**Status:** Paused — not a current priority.  
**Canonical repo:** `~/govbid` only (`~/rs` duplicate deleted 2026-06-10).

## Why paused

GovBid infrastructure was mid-migration from **Docker Desktop** to **AWS**. The daily pipeline partially works on legacy Postgres, but AWS cutover is incomplete. Work stops here until GovBid becomes a priority again.

## What was done

| Item | Result |
|------|--------|
| Duplicate `~/rs` removed | Done — single repo at `~/govbid` |
| AWS migration docs | [aws-deploy.md](aws-deploy.md) |
| Terraform RDS scaffold | `terraform/` (not successfully applied) |
| `scripts/apply_migrations.sh` | Added — requires `psql` |
| `run_daily.sh` (2026-06-10) | Download + ingest **OK** (4,743 opportunities) |
| Terraform `apply` | **Failed** — free-tier backup retention |
| RDS migrations | **Not run** — `psql` not installed |
| `doctor.sh` / status step | **Hung** — still Docker-dependent |

## Blockers when resuming

1. **Terraform RDS** — `backup_retention_period = 7` exceeds AWS free tier. Set to `0` or `1` in `terraform/rds.tf`, then `terraform apply`.
2. **Install psql** — `sudo apt install postgresql-client`, then `bash scripts/apply_migrations.sh`.
3. **Update `.env`** — `POSTGRES_HOST` = RDS endpoint from `terraform output -raw postgres_endpoint`, `POSTGRES_PORT=5432`.
4. **Retire Docker checks** — `scripts/doctor.sh` and `scripts/status.sh` assume Docker + n8n; need RDS-aware path or skip doctor when on AWS.
5. **Phase 2 (later)** — n8n + Counsel on App Runner/ECS or n8n Cloud.

## Where data lives today

- **Postgres:** Still likely **local/Docker** on `localhost:5433` (ingest succeeded without RDS).
- **SAM CSV:** `data/` (gitignored).
- **Cron:** WSL crontab may still point at `~/govbid` — verify before relying on it.

## Resume checklist (start here)

```bash
cd ~/govbid
git pull   # if pushed

# 1. Fix Terraform + RDS
cd terraform
# Fix backup_retention_period in rds.tf (free tier: 0 or 1)
terraform apply
terraform output -raw postgres_endpoint

# 2. Point .env at RDS
# POSTGRES_HOST=<endpoint>
# POSTGRES_PORT=5432

# 3. Schema
sudo apt install -y postgresql-client
bash scripts/apply_migrations.sh

# 4. Smoke test (skip hung doctor until fixed)
./run_download.sh && ./run_ingest.sh
uv run scripts/review_queue.py

# 5. Read aws-deploy.md for Phase 2 (n8n, Counsel)
```

## Related docs

- [aws-deploy.md](aws-deploy.md) — AWS target architecture
- [STATUS.md](STATUS.md) — phase gates (last verified 2026-05-31 on Docker)
- [README.md](../README.md) — setup entry
