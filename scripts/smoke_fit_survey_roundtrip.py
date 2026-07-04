#!/usr/bin/env python3
"""Smoke-test creating + (optionally) indexing a counsel_fit_surveys row."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row

from counsel.config import load_env, postgres_params
from counsel import db, rag
from counsel.survey_schema import chunk_id_for_fit_survey, survey_row_to_rag_text


def _select_notice_id(conn: psycopg.Connection[Any]) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.notice_id
            FROM opportunities o
            JOIN match_scores m ON m.opportunity_id = o.id
            WHERE o.active = TRUE
              AND o.source LIKE 'federal:%'
              AND m.review_status = 'pending'
            ORDER BY m.rule_score DESC NULLS LAST
            LIMIT 1;
            """
        )
        row = cur.fetchone()
        return str(row["notice_id"]) if row else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", action="store_true", help="Also index into Chroma (requires OPENAI_API_KEY)")
    args = parser.parse_args()

    load_env()
    openai_key = os.environ.get("OPENAI_API_KEY") or ""
    if args.index and not openai_key.strip():
        print("OPENAI_API_KEY not set; skipping indexing.", file=sys.stderr)
        args.index = False

    with psycopg.connect(**postgres_params(), row_factory=dict_row) as conn:
        notice_id = _select_notice_id(conn)
        if not notice_id:
            print("No pending notice_id found for smoke test.", file=sys.stderr)
            return 1

        saved = db.save_fit_survey(
            notice_id,
            "pending",
            fit_rating=3,
            score_accurate=True,
            score_direction="about_right",
            good_tags=[],
            bad_tags=[],
            good_notes="verify_phase3 smoke",
            bad_notes=None,
            lessons_learned=None,
        )
        survey_id = saved.get("id")
        if not survey_id:
            print("save_fit_survey returned empty id.", file=sys.stderr)
            return 1

        indexed_ok = False
        if args.index:
            row = db.get_fit_survey_by_id(int(survey_id))
            if row:
                rag.index_chunks(
                    [
                        {
                            "id": chunk_id_for_fit_survey(int(survey_id)),
                            "text": survey_row_to_rag_text(row),
                            "source": f"fit_feedback/survey_{survey_id}",
                            "title": "fit_feedback",
                        }
                    ],
                    reset=False,
                )
                db.mark_fit_survey_indexed(int(survey_id))
                indexed_ok = True

        # cleanup
        with conn.cursor() as cur:
            cur.execute("DELETE FROM counsel_fit_surveys WHERE id=%s", (int(survey_id),))
        conn.commit()

        print(f"survey_id={survey_id} indexed_ok={indexed_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

