# Opportunity dashboard

**Prerequisite:** Phase 1 pass — `bash scripts/verify_phase1.sh`. Phase 2 gate: `bash scripts/verify_phase2.sh`. See [STATUS.md](STATUS.md).

## Primary UI — Counsel (Streamlit)

```bash
./run_counsel.sh
```

Open **http://127.0.0.1:8501**

### How it works (in the app)

1. Counsel pulls active federal **solicitations** from SAM.gov (updated daily).
2. It ranks them against **your company profile** — industry codes, keywords, location, set-asides.
3. You review **Today's matches** — save promising ones, pass on the rest.

A *solicitation* is a government request for goods or services your company might bid on.

### Tabs

| Tab | Use |
|-----|-----|
| **Today's matches** | Ranked opportunities as cards; **Save for review**, **Pursuing**, or **Not for us** |
| **Saved opportunities** | Items you saved or marked pursuing (aim for 3–5 active pursuits) |
| **Your company profile** | Home states, industry codes (NAICS), keywords, set-asides |
| **Ask Counsel** | Capture copilot — strategy, briefings, pass/bid advice |
| **Search all** | Browse the full database when you need to look outside today's list |
| **Rate a match** | Feedback after pass/pursue — improves future recommendations |

### Sidebar (beginner-friendly)

| Control | Meaning |
|---------|---------|
| **Show me** | How many opportunities to list (10 / 25 / 50) |
| **Deadlines** | Only show solicitations due in the next 2 weeks, 30 days, or 90 days |
| **Match quality** | Best / Good / Worth a look — how strongly each row matches your profile |

**Advanced filters** (collapsed by default): exact count, exact day window, pipeline counts.

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
