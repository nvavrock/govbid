# govbid

Federal contract opportunity tooling (SAM.gov bulk download, filtering, GovClose training transcripts).

## SAM.gov daily download

```bash
/home/me/govbid/run_download.sh
```

Cron (daily 6 AM): `0 6 * * * /home/me/govbid/run_download.sh`

Output: `data/ContractOpportunitiesFull_YYYYMMDD.csv` (only the latest file is kept).

## GovClose YouTube transcripts

Fetches English captions from [@govclose](https://www.youtube.com/@govclose/videos).

**Prerequisite:** install [yt-dlp](https://github.com/yt-dlp/yt-dlp):

```bash
sudo apt update && sudo apt install -y yt-dlp
# or: uv tool install yt-dlp   # installs to ~/.local/bin
yt-dlp --version
```

**Run:**

```bash
/home/me/govbid/run_govclose_transcripts.sh
```

**Smoke test (first 3 videos only):**

```bash
PLAYLIST_END=3 /home/me/govbid/scripts/fetch_govclose_transcripts.sh
```

Output:

- `transcripts/govclose/{date}_{id}_{title}.txt` — one file per video
- `transcripts/govclose/govclose_all.txt` — combined archive with headers

Re-runs skip already-archived videos (`transcripts/govclose/.archive.txt`).
