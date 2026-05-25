#!/usr/bin/env python3
"""Aggregate Consig pass/bid feedback and suggest match-profile tuning (human applies)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from consig.config import load_env  # noqa: E402
from consig import db  # noqa: E402


def main() -> int:
    load_env()
    db.ensure_consig_schema()

    import psycopg
    from psycopg.rows import dict_row

    from consig.config import postgres_params

    sql = """
        SELECT f.action, f.user_reason, f.notice_id, o.title, o.agency, m.match_reasons
        FROM consig_feedback f
        LEFT JOIN opportunities o ON o.notice_id = f.notice_id
        LEFT JOIN match_scores m ON m.opportunity_id = o.id
        ORDER BY f.created_at DESC
        LIMIT 200
    """
    with psycopg.connect(**postgres_params(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            records = cur.fetchall()

    if not records:
        print("No consig_feedback rows yet. Mark pass/bid in Consig chat to collect reasons.")
        return 0

    print("=== Consig feedback report ===\n")
    by_action = Counter(r["action"] for r in records)
    print("Actions:", dict(by_action))

    pass_rows = [r for r in records if r["action"] == "pass" and r.get("user_reason")]
    if pass_rows:
        print("\n--- Recent pass reasons ---")
        for r in pass_rows[:15]:
            print(f"  • {r.get('notice_id', '')[:12]}… — {(r.get('user_reason') or '')[:80]}")
            print(f"    title: {(r.get('title') or '')[:60]}")
            print(f"    reasons: {r.get('match_reasons')}")

    print("\n--- Suggested profile review (manual) ---")
    print("  1. Review exclude_keywords in config/match-profile.yaml for repeated pass themes.")
    print("  2. Review exclude_set_asides if passes cite set-aside mismatch.")
    print("  3. Adjust review.min_score if queue quality is too low/high.")
    print("  4. Re-run ./run_ingest.sh only after profile/SQL changes — scores refresh via refresh_match_scores().")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
