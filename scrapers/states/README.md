# State / Local Contract Scrapers (Phase 2)

Add one state portal at a time. Each portal gets its own folder under `scrapers/states/<code>/`.

## Playbook (repeat per state)

### 1. Select portal

Examples:

| State | Portal | Notes |
|-------|--------|-------|
| CA | [eProcure](https://caleprocure.ca.gov/) | Check ToS before automating |
| TX | [ESBD](https://www.txsmartbuy.gov/) | May require login for some data |
| FL | [MyFloridaMarketPlace](https://vendor.myfloridamarketplace.com/) | Review robots.txt |

### 2. Legal check (required)

Before writing code, document in `<state>/README.md`:

- Terms of Service — is automated access allowed?
- `robots.txt` — disallowed paths?
- Rate limits — be conservative (1 request / 2–5 seconds)
- Authentication — if login required, prefer manual export or official API

**If scraping is prohibited:** use email alerts from the portal, or manual CSV export into `data/state-imports/`.

### 3. Implement scraper

```
scrapers/states/<code>/
├── README.md          # ToS notes, portal URL, field mapping
├── scrape.py          # Python 3.11+ (httpx + BeautifulSoup or Playwright)
└── requirements.txt   # optional local venv
```

**Output schema** — map to the same `opportunities` table:

| Field | Example |
|-------|---------|
| `notice_id` | State-unique ID |
| `source` | `state:CA` |
| `title` | Solicitation title |
| `response_deadline` | ISO timestamp |
| `naics` | If available |
| `agency` | Issuing department |
| `ui_link` | Detail page URL |
| `raw_data` | Full parsed JSON |

### 4. n8n integration

Create a separate workflow (do not merge with SAM bulk ingest):

1. Schedule trigger (e.g. daily 4 AM)
2. **Execute Command** — `python3 /scrapers/states/ca/scrape.py` (mount repo into n8n container), **or**
3. **HTTP Request** + **HTML** nodes for simple static pages
4. Postgres upsert with `source = 'state:XX'`
5. `SELECT refresh_match_scores();`

Mount scrapers in `docker-compose.yml` when ready:

```yaml
n8n:
  volumes:
    - ./scrapers:/scrapers:ro
```

### 5. Template scraper

Copy `scrapers/states/_template/` when adding a new state (see `_template/scrape.py`).

### 6. Verify

```sql
SELECT source, COUNT(*) FROM opportunities GROUP BY source;
```

Ensure state rows appear with correct `source` prefix and pass `review_queue.sql`.

## Federal reminder

**Never scrape SAM.gov.** Use workflows `01` and `02` only.
