# n8n Workflow Imports

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

## Consig API (optional digest summaries)

When `consig-api` is running (`docker compose up` or `./run_consig_api.sh`), workflow `04-review-digest.json` can call:

- `POST http://consig-api:8000/chat` with body `{"briefing": true}` for a narrative summary of today's queue
- `GET http://consig-api:8000/queue` for raw rows

Requires `OPENAI_API_KEY` in `.env` and a built index (`uv run scripts/build_consig_index.py`).
