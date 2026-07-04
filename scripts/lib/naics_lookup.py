"""2022 NAICS titles and sector hierarchy (Census structure file)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NAICS_JSON = ROOT / "config" / "naics2022.json"


@lru_cache(maxsize=1)
def load_naics() -> dict:
    if not NAICS_JSON.is_file():
        return {"sectors": {}, "codes": {}, "hierarchy": []}
    return json.loads(NAICS_JSON.read_text(encoding="utf-8"))


def sector_options() -> list[tuple[str, str]]:
    data = load_naics()
    sectors = data.get("sectors") or {}
    return sorted((code, f"{code} — {title}") for code, title in sectors.items())


def title_for_code(code: str | None) -> str | None:
    if not code:
        return None
    data = load_naics()
    codes = data.get("codes") or {}
    entry = codes.get(code.strip())
    return entry.get("title") if entry else None


def label_for_code(code: str | None) -> str:
    if not code:
        return ""
    title = title_for_code(code)
    return f"{code} — {title}" if title else code


def codes_for_sector(sector: str, *, in_database: set[str] | None = None) -> list[tuple[str, str]]:
    """Six-digit codes under a 2-digit sector, optionally limited to codes in DB."""
    data = load_naics()
    codes = data.get("codes") or {}
    out: list[tuple[str, str]] = []
    for code, meta in sorted(codes.items()):
        if not code.startswith(sector):
            continue
        if in_database is not None and code not in in_database:
            continue
        out.append((code, label_for_code(code)))
    return out


def search_codes(
    query: str,
    *,
    sector: str | None = None,
    in_database: set[str] | None = None,
    limit: int = 100,
) -> list[tuple[str, str]]:
    q = query.strip().lower()
    data = load_naics()
    codes = data.get("codes") or {}
    results: list[tuple[str, str]] = []
    for code, meta in sorted(codes.items()):
        if sector and not code.startswith(sector):
            continue
        if in_database is not None and code not in in_database:
            continue
        title = (meta.get("title") or "").lower()
        if q and q not in code and q not in title:
            continue
        results.append((code, label_for_code(code)))
        if len(results) >= limit:
            break
    return results
