#!/usr/bin/env bash
# GovClose (@govclose) YouTube transcript fetcher
#
# Prerequisites:
#   yt-dlp — install once:
#     sudo apt update && sudo apt install -y yt-dlp
#     or: pipx install yt-dlp
#   Verify: yt-dlp --version
#
# Limitations:
#   - Videos without captions are skipped
#   - Auto-generated English subs used when manual subs are missing
#   - Private/members-only videos will fail
#
# Usage:
#   ./scripts/fetch_govclose_transcripts.sh
#   PLAYLIST_END=3 ./scripts/fetch_govclose_transcripts.sh   # smoke test (first N videos)

set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$PROJECT/transcripts/govclose"
ARCHIVE="$OUT_DIR/.archive.txt"
CHANNEL_URL="https://www.youtube.com/@govclose/videos"
COMBINED="$OUT_DIR/govclose_all.txt"

mkdir -p "$OUT_DIR"

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "Error: yt-dlp not found. Install with: sudo apt install -y yt-dlp" >&2
  exit 1
fi

vtt_to_txt() {
  local vtt="$1" txt="$2"
  python3 - "$vtt" "$txt" <<'PY'
import re
import sys

vtt_path, txt_path = sys.argv[1], sys.argv[2]
lines: list[str] = []
with open(vtt_path, encoding="utf-8", errors="replace") as f:
    for raw in f:
        line = re.sub(r"<[^>]+>", "", raw.strip())
        if not line or line == "WEBVTT":
            continue
        if "-->" in line or line.startswith("NOTE") or line.startswith("STYLE"):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
with open(txt_path, "w", encoding="utf-8") as out:
    out.write("\n".join(lines))
    if lines:
        out.write("\n")
PY
}

normalize_subs() {
  shopt -s nullglob
  for vtt in "$OUT_DIR"/*.vtt; do
    [[ -f "$vtt" ]] || continue
    base="${vtt%.vtt}"
    base="${base%.en-orig}"
    base="${base%.en}"
    target="${base}.txt"
    vtt_to_txt "$vtt" "$target"
    rm -f "$vtt"
  done
  for enfile in "$OUT_DIR"/*.en.txt; do
    base="${enfile%.en.txt}"
    target="${base}.txt"
    if [[ ! -f "$target" ]] || [[ "$enfile" -nt "$target" ]]; then
      mv -f "$enfile" "$target"
    else
      rm -f "$enfile"
    fi
  done
  for enfile in "$OUT_DIR"/*.en.txt; do
    base="${enfile%.en.txt}"
    [[ -f "${base}.txt" ]] && rm -f "$enfile"
  done
  for enfile in "$OUT_DIR"/*.en-orig.txt; do
    base="${enfile%.en-orig.txt}"
    [[ -f "${base}.txt" ]] && rm -f "$enfile"
  done
}

read_info_field() {
  local json="$1" field="$2"
  if command -v jq >/dev/null 2>&1; then
    jq -r "$field // empty" "$json"
  else
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2].lstrip('.')) or '')" "$json" "$field"
  fi
}

build_archive() {
  shopt -s nullglob
  local archive_tmp
  archive_tmp="$(mktemp)"
  : > "$archive_tmp"
  for json in "$OUT_DIR"/*.info.json; do
    [[ "$(basename "$json")" == NA_* ]] && continue
    video_id="$(read_info_field "$json" .id)"
    [[ -n "$video_id" ]] && echo "youtube ${video_id}" >> "$archive_tmp"
  done
  mv -f "$archive_tmp" "$ARCHIVE"
  echo "Updated download archive: $ARCHIVE"
}

merge_transcripts() {
  local combined_tmp
  combined_tmp="$(mktemp)"
  : > "$combined_tmp"

  shopt -s nullglob
  mapfile -t json_files < <(find "$OUT_DIR" -maxdepth 1 -name '*.info.json' | sort)

  if [[ ${#json_files[@]} -eq 0 ]]; then
    echo "Warning: no .info.json files found; nothing to merge." >&2
    rm -f "$combined_tmp"
    return 0
  fi

  for json in "${json_files[@]}"; do
    [[ "$(basename "$json")" == NA_* ]] && continue
    base="${json%.info.json}"
    txt="${base}.txt"
    [[ -f "$txt" ]] || continue

    title="$(read_info_field "$json" .title)"
    video_id="$(read_info_field "$json" .id)"
    upload_date="$(read_info_field "$json" .upload_date)"
    url="$(read_info_field "$json" .webpage_url)"

    [[ -z "$title" ]] && title="Unknown"
    [[ -z "$url" && -n "$video_id" ]] && url="https://www.youtube.com/watch?v=${video_id}"

    {
      echo "================================================================================"
      echo "Title:   ${title}"
      echo "Video:   ${url}"
      echo "Date:    ${upload_date}"
      echo "================================================================================"
      cat "$txt"
      echo ""
      echo ""
    } >> "$combined_tmp"
  done

  mv -f "$combined_tmp" "$COMBINED"
  echo "Wrote combined transcript: $COMBINED"
}

YTDLP_ARGS=(
  --skip-download
  --write-auto-subs
  --write-subs
  --write-info-json
  --sub-langs "en.*,en"
  --convert-subs vtt
  --sleep-interval 1
  --max-sleep-interval 3
  --ignore-errors
  --download-archive "$ARCHIVE"
  -o "$OUT_DIR/%(upload_date)s_%(id)s_%(title).80B.%(ext)s"
)

if [[ -n "${PLAYLIST_END:-}" ]]; then
  YTDLP_ARGS+=(--playlist-end "$PLAYLIST_END")
  echo "Smoke-test mode: limiting to first ${PLAYLIST_END} video(s)."
fi

echo "Fetching subtitles from ${CHANNEL_URL} ..."
yt-dlp "${YTDLP_ARGS[@]}" "$CHANNEL_URL"

echo "Normalizing subtitle filenames ..."
normalize_subs

echo "Building combined transcript ..."
merge_transcripts

echo "Updating download archive ..."
build_archive

echo "Done. Per-video transcripts in: ${OUT_DIR}"
