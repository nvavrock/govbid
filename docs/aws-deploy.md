# AWS deployment (target)

**Canonical repo:** `~/govbid` only — local duplicate `~/rs` was removed (2026-06-10).

GovBid is moving off **Docker Desktop** to **AWS managed services**. Docker Compose remains optional for offline local dev until AWS cutover is complete.

## Service mapping

| Component | Docker (legacy local) | AWS target |
|-----------|----------------------|------------|
| Postgres | `postgres` container :5433 | **RDS PostgreSQL 16** (`terraform/rds.tf`) |
| n8n | `n8n` container :5678 | **ECS Fargate** or n8n Cloud (Phase 2) |
| Counsel API | `counsel-api` :8000 | **App Runner** or **Lambda + API Gateway** |
| Counsel UI | `counsel-ui` :8501 | **App Runner** (Streamlit) |
| Adminer | container :8081 | **RDS Query Editor** or local `psql` |
| Daily cron | WSL `crontab` | **EventBridge + Lambda** or keep WSL cron → RDS |

## Phase 1 — RDS (now)

1. AWS CLI configured (`~/.aws` — already symlinked from Windows).
2. Copy Terraform vars:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit: postgres_password, admin_cidr (your IP/32 for dev)
   ```
3. Apply RDS:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```
4. Update `.env`:
   ```bash
   POSTGRES_HOST=<rds_endpoint from terraform output>
   POSTGRES_PORT=5432
   ```
5. Run migrations (one-time on fresh RDS):
   ```bash
   bash scripts/apply_migrations.sh   # uses psql against POSTGRES_HOST
   ```
6. Point Python ingest / Counsel at RDS — no Docker required for Postgres.

## Phase 2 — Compute (next)

- Build Counsel image → **ECR** → **App Runner** (same pattern as `~/production` week 1).
- n8n: evaluate **n8n Cloud** vs self-hosted on ECS (workflows in `workflows/n8n/`).

## Phase 3 — Retire Docker

When RDS + compute run in AWS:

1. Stop local stack: `docker compose down` (if still running).
2. Remove Docker Desktop from Windows (optional).
3. Update [STATUS.md](STATUS.md) ops snapshot to AWS endpoints.
4. Archive `docker-compose.yml` to `docs/archive/` or keep labeled **legacy local only**.

## WSL daily pipeline (unchanged logic)

Cron on WSL can stay — it only needs `POSTGRES_HOST` pointing at RDS:

```bash
./run_daily.sh      # download + ingest → RDS
./run_digest.sh     # Slack digest
./run_counsel.sh     # local Streamlit → RDS + OpenAI
```

## Security notes

- Never commit `terraform.tfvars` or `.env`.
- RDS security group allows `5432` from `admin_cidr` only — tighten to your IP/32.
- Use **Secrets Manager** for production passwords (Terraform Phase 2).

## Related

- [STATUS.md](STATUS.md) — migration status
- [sdlc.md](sdlc.md) — deploy stage
- `terraform/README.md` — IaC details
