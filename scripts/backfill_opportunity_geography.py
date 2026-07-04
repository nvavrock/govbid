#!/usr/bin/env python3
"""Backfill state_code, place_of_performance, and work_mode from raw_data."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.geography import (  # noqa: E402
    classify_work_mode,
    place_of_performance_from_row,
    state_code_from_row,
)


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def connect():
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD not set")
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "govbid"),
        password=password,
        dbname=os.environ.get("POSTGRES_DB", "govbid"),
    )


def main() -> int:
    load_env()
    updated = 0
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, state_code, place_of_performance, work_mode, raw_data
                FROM opportunities
                WHERE source LIKE 'federal:%%' AND raw_data IS NOT NULL
                """
            )
            rows = cur.fetchall()
            for opp_id, title, _, _, _, raw_data in rows:
                if isinstance(raw_data, str):
                    raw = json.loads(raw_data)
                else:
                    raw = raw_data or {}
                state = state_code_from_row(raw)
                pop = place_of_performance_from_row(raw)
                desc = raw.get("Description") or raw.get("description") or ""
                mode = classify_work_mode(
                    title=title,
                    description=str(desc) if desc else None,
                    state_code=state,
                )
                cur.execute(
                    """
                    UPDATE opportunities
                    SET state_code = %s,
                        place_of_performance = %s,
                        work_mode = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (state, pop, mode, opp_id),
                )
                updated += 1
        conn.commit()
    print(f"Backfilled geography on {updated:,} opportunities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
