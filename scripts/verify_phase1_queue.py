#!/usr/bin/env python3
"""Emit shell-friendly vars + sample queue for verify_phase1.sh."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.match_profile import load_profile  # noqa: E402
from lib.review_queue_lib import get_review_queue  # noqa: E402


def main() -> int:
    review = load_profile()["review"]
    rows = get_review_queue()
    qcount = len(rows)
    print(f"qcount={qcount}")
    print(f"min_score={review['min_score']}")
    print(f"days_ahead={review['days_ahead']}")
    print(f"top_n={review['top_n']}")
    if rows:
        top = rows[0]
        score = int(top.get("rule_score") or 0)
        link = (top.get("ui_link") or "").strip()
        print(f"top_score={score}")
        print(f"top_score_ok={1 if score >= review['min_score'] and (top.get('fit_band') or 'none') != 'none' else 0}")
        print(f"top_link_ok={1 if link.startswith('http') else 0}")
    print("--- sample ---")
    for i, row in enumerate(rows[:5], 1):
        title = (row.get("title") or "")[:70]
        print(f"{i}. [{row.get('fit_band', 'n/a')}] {title}")
        print(f"   {row.get('agency', '')} | deadline {row.get('response_deadline', 'n/a')}")
    print("--- end ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
