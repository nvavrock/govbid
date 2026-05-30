# State Scraper Template — REPLACE_ME

## Portal

- **URL:** https://example.gov/procurement
- **ToS reviewed:** YYYY-MM-DD
- **Automation allowed:** yes / no / unclear
- **robots.txt:** `/path` disallowed or none

## Field mapping

| Portal field | `opportunities` column |
|--------------|------------------------|
| id | notice_id |
| title | title |
| due_date | response_deadline |
| department | agency |

## Run locally

```bash
cd scrapers/states/_template
python3 scrape.py --dry-run
```

## n8n

Import workflow `05-state-TEMPLATE.json` (create when implementing a real state).
