#!/usr/bin/env python3
"""Index Consig fit surveys into Chroma for RAG explanations.

Reads consig_fit_surveys where indexed_at IS NULL by default.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from consig import db, rag  # noqa: E402
from consig.survey_schema import survey_row_to_rag_text  # noqa: E402


def _chunk_id(survey_id: int) -> str:
    return hashlib.sha256(f"fit_survey:{survey_id}".encode()).hexdigest()[:24]


def _build_chunks(surveys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for s in surveys:
        sid = int(s["id"])
        chunks.append(
            {
                "id": _chunk_id(sid),
                "text": survey_row_to_rag_text(s),
                "source": f"fit_feedback/survey_{sid}",
                "title": "fit_feedback",
            }
        )
    return chunks


def index_surveys(surveys: list[dict[str, Any]], *, reset: bool = False) -> int:
    if not surveys:
        return 0

    chunks = _build_chunks(surveys)
    rag.index_chunks(chunks, reset=reset)

    indexed = 0
    for s in surveys:
        db.mark_fit_survey_indexed(int(s["id"]))
        indexed += 1
    return indexed


def main() -> int:
    parser = argparse.ArgumentParser(description="Index Consig fit surveys into Chroma.")
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild fit feedback collection")
    parser.add_argument("--all", action="store_true", help="Index all fit surveys (may require re-run)")
    parser.add_argument("--survey-id", type=int, default=None, help="Index a single survey id")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be indexed only")
    args = parser.parse_args()

    if args.survey_id is not None:
        if args.dry_run:
            unindexed = db.list_unindexed_fit_surveys()
            matches = [s for s in unindexed if int(s["id"]) == int(args.survey_id)]
            print(f"(dry-run) survey-id={args.survey_id} unindexed_match_count={len(matches)}")
            return 0
        unindexed = db.list_unindexed_fit_surveys()
        matches = [s for s in unindexed if int(s["id"]) == int(args.survey_id)]
        if not matches:
            print(f"No unindexed fit survey id={args.survey_id}.", file=sys.stderr)
            return 1
        return index_surveys(matches, reset=args.reset)

    if args.all:
        surveys = db.list_fit_surveys(limit=5000)
        if not args.reset:
            surveys = [s for s in surveys if s.get("indexed_at") is None]
        if args.dry_run:
            print(f"(dry-run) would index {len(surveys)} fit survey(s) into Chroma.")
            return 0
        indexed = index_surveys(surveys, reset=args.reset)
        print(f"Indexed {indexed} fit survey(s) into Chroma.")
        return 0

    unindexed = db.list_unindexed_fit_surveys()
    if args.dry_run:
        print(f"(dry-run) would index {len(unindexed)} fit survey(s) into Chroma.")
        return 0

    indexed = index_surveys(unindexed, reset=args.reset)
    print(f"Indexed {indexed} fit survey(s) into Chroma.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

