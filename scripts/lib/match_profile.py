"""Load config/match-profile.yaml — single source of truth for ingest, scoring, and review queue."""

from __future__ import annotations

import os
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
    ingest = data.get("ingest") or {}
    profile_block = data.get("profile") or {}
    ingest_mode = (
        os.environ.get("INGEST_MODE", "").strip().lower()
        or str(ingest.get("mode", "full")).strip().lower()
    )
    if ingest_mode not in ("full", "filtered"):
        ingest_mode = "full"
    return {
        "profile_name": profile_block.get("name") or "Default profile",
        "profile_slug": profile_block.get("slug") or "default",
        "capabilities": profile_block.get("capabilities") or "",
        "naics_codes": list(data.get("naics_codes") or []),
        "psc_prefixes": list(data.get("psc_prefixes") or []),
        "include_keywords": list(data.get("include_keywords") or []),
        "exclude_keywords": list(data.get("exclude_keywords") or []),
        "exclude_set_asides": list(data.get("exclude_set_asides") or []),
        "procurement_types": list(data.get("procurement_types") or []),
        "ingest_mode": ingest_mode,
        "review": {
            "days_ahead": int(review.get("days_ahead", 30)),
            "min_score": int(review.get("min_score", 0)),
            "top_n": int(review.get("top_n", 25)),
            "require_match_reasons": bool(review.get("require_match_reasons", True)),
        },
        "geography": {
            "home_states": list((data.get("geography") or {}).get("home_states") or []),
            "include_remote": bool((data.get("geography") or {}).get("include_remote", True)),
            "include_unknown_location": bool(
                (data.get("geography") or {}).get("include_unknown_location", False)
            ),
        },
    }


def profile_meta(profile: dict[str, Any] | None = None) -> dict[str, str]:
    p = profile or load_profile()
    return {
        "name": p.get("profile_name") or "Default profile",
        "slug": p.get("profile_slug") or "default",
        "capabilities": p.get("capabilities") or "",
    }


def is_active_row(active: str | None) -> bool:
    if not active:
        return True
    return active.strip().lower() in ("yes", "y", "true", "1", "active")


def should_ingest_row(
    *,
    notice_id: str | None,
    naics: str | None,
    psc: str | None,
    title: str | None,
    active: str | None,
    profile: dict[str, Any] | None = None,
) -> bool:
    if not notice_id:
        return False
    if not is_active_row(active):
        return False
    p = profile or load_profile()
    if p.get("ingest_mode") == "filtered":
        return passes_ingest_filter(naics, psc, title, p)
    return True


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
