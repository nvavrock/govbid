#!/usr/bin/env python3
"""Aggregate Counsel pass/bid feedback and suggest match-profile tuning (human applies)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from counsel.config import load_env  # noqa: E402
from counsel import db  # noqa: E402


def main() -> int:
    load_env()
    db.ensure_counsel_schema()

    import psycopg
    from psycopg.rows import dict_row

    from counsel.config import postgres_params

    sql = """
        SELECT f.action, f.user_reason, f.notice_id, o.title, o.agency, m.match_reasons
        FROM counsel_feedback f
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
        print("No counsel_feedback rows yet. Mark pass/bid in Counsel chat to collect reasons.")
        return 0

    print("=== Counsel feedback report ===\n")
    by_action = Counter(r["action"] for r in records)
    print("Actions:", dict(by_action))

    pass_rows = [r for r in records if r["action"] == "pass" and r.get("user_reason")]
    if pass_rows:
        print("\n--- Recent pass reasons ---")
        for r in pass_rows[:15]:
            print(f"  • {r.get('notice_id', '')[:12]}… — {(r.get('user_reason') or '')[:80]}")
            print(f"    title: {(r.get('title') or '')[:60]}")
            print(f"    reasons: {r.get('match_reasons')}")

    # --- Fit survey patterns (human grading about project fit) ---
    try:
        sql2 = """
            SELECT bad_tags, score_direction, score_accurate, fit_rating, rule_score
            FROM counsel_fit_surveys
            ORDER BY created_at DESC
            LIMIT 300
        """
        with psycopg.connect(**postgres_params(), row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql2)
                fit_rows = cur.fetchall()
    except Exception:
        fit_rows = []

    if fit_rows:
        print("\n--- Fit survey patterns (manual) ---")
        bad_tag_counter: Counter[str] = Counter()
        score_dir_counter: Counter[str] = Counter()
        accurate_counter: Counter[str] = Counter()
        ratings = []

        for r in fit_rows:
            ratings.append(int(r.get("fit_rating") or 0))
            sd = r.get("score_direction")
            if sd:
                score_dir_counter[str(sd)] += 1
            acc = r.get("score_accurate")
            if acc is True:
                accurate_counter["true"] += 1
            elif acc is False:
                accurate_counter["false"] += 1

            # bad_tags is JSONB → typically a Python list (db driver dependent).
            bad_tags = r.get("bad_tags") or []
            if isinstance(bad_tags, str):
                bad_tags = []
            if isinstance(bad_tags, list):
                for t in bad_tags:
                    bad_tag_counter[str(t)] += 1

        top_bad = bad_tag_counter.most_common(8)
        if top_bad:
            print("Top bad tags:", dict(top_bad))
        if score_dir_counter:
            print("Score direction:", dict(score_dir_counter.most_common(6)))
        if accurate_counter:
            print("Score accurate:", dict(accurate_counter.most_common(2)))
        if ratings:
            avg = sum(ratings) / len(ratings)
            print(f"Average fit_rating: {avg:.2f} ({len(ratings)} survey(s))")

        # Actionable suggestions (human applies via match-profile.yaml tuning).
        if bad_tag_counter.get("wrong_set_aside", 0) >= 2:
            print(
                "Suggestion: multiple surveys cite wrong_set_aside → review config/match-profile.yaml exclude_set_asides."
            )
        if bad_tag_counter.get("hardware_only", 0) >= 2:
            print(
                "Suggestion: multiple surveys cite hardware_only → review config/match-profile.yaml exclude_keywords / include_keywords for software vs hardware intent."
            )
        if bad_tag_counter.get("score_too_high", 0) >= 2 or score_dir_counter.get("too_high", 0) >= 2:
            print(
                "Suggestion: several surveys say score too high → review review.min_score (and/or your include/exclude keyword lists)."
            )

    print("\n--- Suggested profile review (manual) ---")
    print("  1. Review exclude_keywords in config/match-profile.yaml for repeated pass themes.")
    print("  2. Review exclude_set_asides if passes cite set-aside mismatch.")
    print("  3. Adjust review.min_score if queue quality is too low/high.")
    print("  4. Re-run ./run_ingest.sh only after profile/SQL changes — scores refresh via refresh_match_scores().")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
