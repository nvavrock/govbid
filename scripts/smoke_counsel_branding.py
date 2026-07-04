#!/usr/bin/env python3
"""Smoke test for Counsel third-party branding sanitization."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from counsel.branding import sanitize_rag_hit, sanitize_source_label, sanitize_user_facing  # noqa: E402


def _vendor_brand() -> str:
    return "Gov" + "Close"


def _vendor_domain() -> str:
    return "gov" + "close.com"


def main() -> int:
    failures = 0
    brand = _vendor_brand()
    domain = _vendor_domain()

    def check(label: str, ok: bool) -> None:
        nonlocal failures
        if ok:
            print(f"OK   {label}")
        else:
            print(f"FAIL {label}", file=sys.stderr)
            failures += 1

    sample = f"I use the {brand} training corpus from {domain} for guidance."
    cleaned = sanitize_user_facing(sample)
    check("vendor brand removed from user-facing text", brand.lower() not in cleaned.lower())
    check("GovCon preserved", "GovCon" in sanitize_user_facing("GovCon strategy"))

    hit = sanitize_rag_hit(
        {"text": f"{brand} teaches pipeline strategy.", "source": "combined.txt", "title": "x"}
    )
    check("RAG hit text sanitized", brand.lower() not in hit["text"].lower())
    check("RAG source aliased", hit["source"] == "capture_training.txt")
    check("combined.txt alias", sanitize_source_label("combined.txt") == "capture_training.txt")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
