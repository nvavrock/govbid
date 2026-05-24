# govbid

Federal contract opportunity tooling: SAM.gov bulk download, GovClose training corpus, and agent-assisted capture planning.

## Project layout

```
govbid/
├── README.md
├── pyproject.toml              # Python deps (requests); managed with uv
├── run_download.sh             # daily SAM.gov CSV pull
├── run_govclose_transcripts.sh # refresh GovClose transcript corpus
├── docs/
│   ├── gameplan.md             # phased build plan (source of truth)
│   ├── gameplan.docx
│   ├── federal_contracting_playbook.md
│   ├── sam_gov_procurement_framework.md
│   └── reference/              # official SAM / entity docs (PDF)
├── scripts/
│   ├── check_env.sh            # preflight sanity checks
│   ├── download_sam_opportunities.py
│   ├── fetch_govclose_transcripts.sh
│   ├── md_to_docx.py
│   └── lib/common.sh
├── data/                       # SAM bulk CSV (gitignored)
├── logs/                       # run logs (gitignored)
└── transcripts/govclose/       # RAG corpus (tracked in git)
```

Related repo: [`govbid-pipeline`](https://github.com/nvavrock/govbid-pipeline) — Docker + n8n + PostgreSQL stack for ingest, scoring, and review queue (Phase 2+).

## Setup

```bash
cd /home/me/rs
uv sync
./scripts/check_env.sh
```

Optional (regenerate Word doc from markdown):

```bash
uv sync --extra docs
uv run --extra docs python scripts/md_to_docx.py
```

## SAM.gov daily download

```bash
/home/me/rs/run_download.sh
```

Cron (daily 6 AM):

```cron
0 6 * * * /home/me/rs/run_download.sh
```

- Output: `data/ContractOpportunitiesFull_YYYYMMDD.csv` (older exports removed automatically)
- Uses atomic `.csv.part` writes, retries, and a minimum file-size check
- Override URL: `SAM_BULK_CSV_URL` (same variable as `govbid-pipeline`)
- Logs: `logs/download.log` (failures exit non-zero for cron alerting)

Manual run:

```bash
uv run scripts/download_sam_opportunities.py --help
```

## GovClose YouTube transcripts

Fetches English captions from [@govclose](https://www.youtube.com/@govclose/videos) for the **Consig** RAG knowledge base.

**Prerequisite:** [yt-dlp](https://github.com/yt-dlp/yt-dlp)

```bash
sudo apt update && sudo apt install -y yt-dlp
yt-dlp --version
```

**Run:**

```bash
/home/me/rs/run_govclose_transcripts.sh
```

**Smoke test (first 3 videos only):**

```bash
PLAYLIST_END=3 /home/me/rs/scripts/fetch_govclose_transcripts.sh
```

Output:

- `transcripts/govclose/{date}_{id}_{title}.txt` — one file per video
- `transcripts/govclose/govclose_all.txt` — combined archive with headers

Re-runs skip already-archived videos (`transcripts/govclose/.archive.txt`, local only).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/gameplan.md](docs/gameplan.md) | Phased roadmap: data → dashboard → agents |
| [docs/federal_contracting_playbook.md](docs/federal_contracting_playbook.md) | Capture strategy, vehicles, SBIR |
| [docs/sam_gov_procurement_framework.md](docs/sam_gov_procurement_framework.md) | SAM.gov lifecycle and compliance |
| [docs/reference/](docs/reference/) | SAM data extract docs, entity checklist |

## Operations notes

- **Lock files** in `logs/` prevent overlapping cron runs.
- **Do not scrape SAM.gov** — use the official bulk extract URL or API only.
- **Regenerate gameplan.docx** after editing `docs/gameplan.md` (see Setup).
