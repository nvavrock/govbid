#!/usr/bin/env python3
"""
Template state procurement scraper.
Copy this folder to scrapers/states/<code>/ and customize.

Usage:
  python3 scrape.py --dry-run
  python3 scrape.py --output ../../data/state-imports/XX.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE = "state:XX"  # e.g. state:CA


def fetch_opportunities() -> list[dict]:
    """Fetch and parse opportunities from the state portal."""
    # TODO: implement with httpx/BeautifulSoup or Playwright
    # Respect ToS and rate limits documented in README.md
    return []


def normalize(raw: dict) -> dict:
    return {
        "notice_id": raw.get("id"),
        "source": SOURCE,
        "title": raw.get("title"),
        "solicitation_number": raw.get("solicitation_number"),
        "posted_date": raw.get("posted_date"),
        "response_deadline": raw.get("response_deadline"),
        "naics": raw.get("naics"),
        "psc": raw.get("psc"),
        "set_aside": raw.get("set_aside"),
        "agency": raw.get("agency"),
        "ui_link": raw.get("url"),
        "active": True,
        "raw_data": raw,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="State procurement scraper template")
    parser.add_argument("--dry-run", action="store_true", help="Print results, do not write file")
    parser.add_argument("--output", help="Write JSON array to this path")
    args = parser.parse_args()

    raw_rows = fetch_opportunities()
    rows = [normalize(r) for r in raw_rows if r.get("id")]

    payload = {
        "source": SOURCE,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "opportunities": rows,
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if not args.output:
        print("Specify --output or use --dry-run", file=sys.stderr)
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"Wrote {len(rows)} opportunities to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
