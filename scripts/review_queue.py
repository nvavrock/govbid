#!/usr/bin/env python3
"""Print top pending opportunities for human review (params from match-profile.yaml)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.match_profile import load_profile  # noqa: E402
from lib.review_queue_lib import get_review_queue  # noqa: E402
from query_lib import print_table  # noqa: E402


def main() -> int:
    rows = get_review_queue()
    print_table(rows)
    review = load_profile()["review"]
    print(
        f"\n(profile: min_score={review['min_score']}, "
        f"days_ahead={review['days_ahead']}, top_n={review['top_n']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
