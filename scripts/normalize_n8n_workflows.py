#!/usr/bin/env python3
"""Add n8n 2.x required fields to workflow JSON files before CLI import."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF_DIR = ROOT / "workflows" / "n8n"


def stable_id(stem: str, suffix: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"govbid.{stem}.{suffix}"))


def normalize(data: dict, stem: str, now: str) -> dict:
    out = dict(data)
    out.setdefault("id", stable_id(stem, "id"))
    out.setdefault("versionId", stable_id(stem, "versionId"))
    out.setdefault("createdAt", now)
    out.setdefault("updatedAt", now)
    out.setdefault("active", False)
    out.setdefault("pinData", {})
    out.setdefault("triggerCount", 0)
    return out


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for path in sorted(WF_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalize(data, path.stem, now)
        path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
        print(f"normalized {path.name}")


if __name__ == "__main__":
    main()
