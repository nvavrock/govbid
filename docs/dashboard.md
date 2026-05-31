# Opportunity dashboard (Phase 2)

**Prerequisite:** Phase 1 pass — `bash scripts/verify_phase1.sh`. Phase 2 gate: `bash scripts/verify_phase2.sh` (needs `SLACK_WEBHOOK_URL` for digest). See [STATUS.md](STATUS.md).

## Primary UI — Consig (Streamlit)

```bash
./run_consig.sh
```

Open **http://127.0.0.1:8501**

| Tab | Use |
|-----|-----|
| **Today's queue** | Profile-driven top N pending opportunities; export CSV; Shortlist / Bid / Pass / Reset |
| **Browse / detail** | Filter by agency, NAICS, status; full row JSON + SAM link |
| **Shortlist** | `reviewing` and `bid` picks (target 3–5 for capture work) |
| **Chat** | Consig copilot for strategy and opportunity briefs |

Queue parameters come from [`config/match-profile.yaml`](../config/match-profile.example.yaml) → `review:` (`min_score`, `days_ahead`, `top_n`). Sidebar sliders override for the session only.

## SQL fallback — Adminer

- URL: **http://localhost:8081**
- Server: `postgres` (Docker network name)
- Port: `5432` (inside Docker; host tools use `5433`)
- User / database / password: from `.env`

Run the saved query [`db/queries/review_queue.sql`](../db/queries/review_queue.sql) for a quick table view. Params in that file are **approximate defaults**; CLI and Consig use `match-profile.yaml` via Python.

Use Adminer when you need ad-hoc SQL, schema inspection, or bulk updates. Use Consig for daily review habits and status changes.

## Daily Slack digest

```bash
bash scripts/send_review_digest.py --dry-run
bash scripts/send_review_digest.py --send   # requires SLACK_WEBHOOK_URL in .env
./run_digest.sh
```

Optional cron (after `./run_daily.sh`):

```bash
bash scripts/install_daily_cron.sh --install
```

Logs: `logs/digest.log`

## Verification

```bash
bash scripts/verify_phase2.sh
```
