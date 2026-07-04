"""Place-of-performance parsing and work-mode classification for SAM opportunities."""

from __future__ import annotations

import re
from typing import Any

REMOTE_KEYWORDS = (
    "remote",
    "telework",
    "virtual",
    "nationwide",
    "nation-wide",
    "anywhere",
    "work from home",
    "wfh",
    "off-site",
    "offsite",
    "fully remote",
    "no on-site",
    "not required to report",
    "conus-wide",
    "continental u.s.",
    "continental us",
    "multiple locations",
    "various locations",
)

US_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)


def normalize_state_code(value: str | None) -> str | None:
    if not value:
        return None
    code = value.strip().upper()
    if len(code) == 2 and code in US_STATE_CODES:
        return code
    return None


def place_of_performance_from_row(row: dict[str, Any]) -> str | None:
    parts = [
        (row.get("PopCity") or row.get("City") or "").strip(),
        (row.get("PopState") or row.get("State") or "").strip(),
        (row.get("PopZip") or row.get("ZipCode") or "").strip(),
    ]
    text = ", ".join(p for p in parts if p)
    return text or None


def state_code_from_row(row: dict[str, Any]) -> str | None:
    for key in ("PopState", "State", "popstate", "state"):
        val = row.get(key)
        if isinstance(val, str):
            code = normalize_state_code(val)
            if code:
                return code
    return None


def classify_work_mode(
    *,
    title: str | None,
    description: str | None = None,
    state_code: str | None = None,
) -> str:
    """Return remote | onsite | unknown."""
    text = f"{title or ''} {description or ''}".lower()
    if any(k in text for k in REMOTE_KEYWORDS):
        return "remote"
    if state_code:
        return "onsite"
    return "unknown"


def passes_geography_filter(
    *,
    state_code: str | None,
    work_mode: str | None,
    home_states: list[str] | None,
    include_remote: bool = True,
    include_unknown_location: bool = False,
) -> bool:
    """True when row should appear for the user's geography preferences."""
    states = [s.strip().upper() for s in (home_states or []) if s and s.strip()]
    if not states:
        return True

    mode = (work_mode or "unknown").lower()
    st = (state_code or "").upper() or None

    if st and st in states:
        return True
    if include_remote and mode == "remote":
        return True
    if include_unknown_location and mode == "unknown":
        return True
    return False
