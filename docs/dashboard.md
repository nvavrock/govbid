# Opportunity dashboard

**Prerequisite:** Phase 1 pass — `bash scripts/verify_phase1.sh`. Phase 2 gate: `bash scripts/verify_phase2.sh`. See [STATUS.md](STATUS.md).

## Primary UI — Counsel (Streamlit)

```bash
./run_counsel.sh
```

Open **http://127.0.0.1:8501**

Personal/operator mode is the default (`COUNSEL_SKIP_ONBOARDING=1`): open straight to **Today's matches**. Set `COUNSEL_SKIP_ONBOARDING=0` only if you want the first-run setup wizard.

### How it works

1. Active federal solicitations from SAM.gov (updated daily).
2. Ranked against your fit profile — NAICS, keywords, geography, set-asides.
3. Review **Today's matches** — save, pursue, or pass.

### Tabs

| Tab | Use |
|-----|-----|
| **Today's matches** | Ranked opportunities as cards; **Save for review**, **Pursuing**, or **Not for us** |
| **Saved** | Items you saved or marked pursuing |
| **Profile** | Home states, NAICS, keywords, set-asides |
| **Ask Counsel** | Capture copilot — strategy, briefings, pass/bid advice |
| **Search all** | Browse the full database outside today's list |
| **Rate a match** | Feedback after pass/pursue |

### Sidebar

| Control | Meaning |
|---------|---------|
| **Profile** | Active fit profile (name shown when only one) |
| **Show me** | How many opportunities to list (10 / 25 / 50) |
| **Deadlines** | Due in next 2 weeks, 30 days, or 90 days |
| **Match quality** | Best / Good / Worth a look |

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
