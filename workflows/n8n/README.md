# n8n Workflow Imports

**Stack:** n8n **2.17+** with owner auto-provisioned from `.env` (see [README.md](../../README.md) setup).

## Automated import (recommended)

```bash
bash scripts/stack-up.sh
bash scripts/provision-n8n.sh
```

This imports the **GovBid Postgres** credential and all workflow JSON files under `workflows/n8n/`.

## Manual import

Import these JSON files in n8n: **Workflows → Import from File**.

After import, for each workflow:

1. Open every **Postgres** node.
2. Create credential **GovBid Postgres** (if missing):
   - Host: `postgres`
   - Database / User / Password: from `.env`
3. Assign the credential to all Postgres nodes.
4. Activate the workflow.

| File | Schedule (ET) |
|------|----------------|
| `01-sam-bulk-ingest.json` | Daily 2:00 |
| `02-sam-api-delta.json` | Daily 6:00 |
| `03-usaspending-enrichment.json` | Sunday 3:00 |
| `04-review-digest.json` | Daily 7:00 |

Credential placeholder ID in exports: `GOVBID_POSTGRES` — n8n will prompt to map on import.

**Matching rules** are embedded in workflow Code nodes (defaults mirror `config/match-profile.example.yaml`). Update workflows and `review_queue.sql` when you change filters.

Workflow `03` upserts `award_enrichment` by `usaspending_award_id` (requires migration `002_award_dedup_and_scoring.sql` on existing databases).

## Review digest (workflow 04)

Workflow `04-review-digest.json` (daily 7:00 AM ET):

1. Queries pending review queue (defaults: min_score 25, days_ahead 30, top 10 in digest).
2. Posts **Slack Block Kit** message if `SLACK_WEBHOOK_URL` is set in n8n environment variables.
3. Writes backup markdown to `/data/review-digest-YYYY-MM-DD.md` in the n8n container.

**Primary digest path (recommended):** host cron via `./run_digest.sh` using `scripts/send_review_digest.py` (reads `config/match-profile.yaml`).

Add to n8n container env in `docker-compose.yml` or n8n UI:

- `SLACK_WEBHOOK_URL` — incoming webhook URL
- `DIGEST_TOP_N` — optional (default 10)

Keep queue SQL params roughly in sync with `match-profile.yaml` → `review:` (same as workflow 01 Code nodes).

## Password / owner changes

Owner credentials come from `.env` (`N8N_OWNER_EMAIL`, `N8N_BASIC_AUTH_PASSWORD`). To change the password:

```bash
bash scripts/reset-n8n-login.sh   # regenerates hash + restarts n8n
```
