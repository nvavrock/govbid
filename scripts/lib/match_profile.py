"""Load config/match-profile.yaml — single source of truth for ingest, scoring, and review queue."""

from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
MATCH_PROFILE = ROOT / "config" / "match-profile.yaml"
MATCH_PROFILE_EXAMPLE = ROOT / "config" / "match-profile.example.yaml"


def load_profile() -> dict[str, Any]:
    import yaml

    path = MATCH_PROFILE if MATCH_PROFILE.is_file() else MATCH_PROFILE_EXAMPLE
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing match profile. Copy: cp config/match-profile.example.yaml config/match-profile.yaml"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    review = data.get("review") or {}
    return {
        "naics_codes": list(data.get("naics_codes") or []),
        "psc_prefixes": list(data.get("psc_prefixes") or []),
        "include_keywords": list(data.get("include_keywords") or []),
        "exclude_keywords": list(data.get("exclude_keywords") or []),
        "exclude_set_asides": list(data.get("exclude_set_asides") or []),
        "procurement_types": list(data.get("procurement_types") or []),
        "review": {
            "days_ahead": int(review.get("days_ahead", 30)),
            "min_score": int(review.get("min_score", 25)),
            "top_n": int(review.get("top_n", 25)),
        },
    }


def passes_ingest_filter(
    naics: str | None,
    psc: str | None,
    title: str | None,
    profile: dict[str, Any] | None = None,
) -> bool:
    """Same rules as ingest pre-filter (NAICS, PSC prefix, or title keywords)."""
    p = profile or load_profile()
    naics_list = p["naics_codes"]
    psc_prefixes = p["psc_prefixes"]
    keywords = p["include_keywords"]
    if naics and naics in naics_list:
        return True
    if psc and any(psc.startswith(prefix) for prefix in psc_prefixes):
        return True
    t = (title or "").lower()
    return any(k in t for k in keywords)
