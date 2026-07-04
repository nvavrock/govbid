#!/usr/bin/env python3
"""Build config/naics2022.json from Census 2022 NAICS Structure (official xlsx)."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "config" / "naics2022.json"
SOURCE_URL = "https://www.census.gov/naics/2022NAICS/2022_NAICS_Structure.xlsx"


def _clean_title(title: str) -> str:
    return re.sub(r"\s*T\s*$", "", title.strip())


def _code_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    return text or None


def _sector_for(code: str) -> str:
    return code[:2] if len(code) >= 2 else code


def main() -> int:
    try:
        import openpyxl
    except ImportError:
        print("Install openpyxl: uv run --with openpyxl python scripts/build_naics_lookup.py", file=sys.stderr)
        return 1

    tmp = ROOT / "data" / "2022_NAICS_Structure.xlsx"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if not tmp.is_file():
        print(f"Downloading {SOURCE_URL} ...")
        import subprocess

        subprocess.run(
            ["curl", "-fsSL", "-o", str(tmp), SOURCE_URL],
            check=True,
        )

    wb = openpyxl.load_workbook(tmp, read_only=True)
    ws = wb.active

    sectors: dict[str, str] = {}
    codes: dict[str, dict[str, str]] = {}
    hierarchy: list[dict[str, str]] = []

    for row in ws.iter_rows(min_row=4, values_only=True):
        if not row or len(row) < 3:
            continue
        code = _code_str(row[1])
        title = _clean_title(str(row[2] or ""))
        if not code or not title:
            continue
        sector = _sector_for(code)
        if len(code) == 2:
            sectors[code] = title
        entry = {"code": code, "title": title, "sector": sector}
        hierarchy.append(entry)
        if len(code) == 6:
            codes[code] = {"title": title, "sector": sector}

    payload = {
        "source": SOURCE_URL,
        "sectors": sectors,
        "codes": codes,
        "hierarchy": hierarchy,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} — {len(sectors)} sectors, {len(codes)} six-digit codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
