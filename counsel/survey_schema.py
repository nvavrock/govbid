"""Fit survey tags and validation for opportunity/project fit feedback."""

from __future__ import annotations

import json
from typing import Any

GOOD_TAGS = frozenset(
    {
        "software_scope",
        "right_naics",
        "agency_fit",
        "deadline_ok",
        "set_aside_ok",
        "size_fit",
    }
)

BAD_TAGS = frozenset(
    {
        "hardware_only",
        "wrong_set_aside",
        "bad_deadline",
        "wrong_agency",
        "too_big",
        "too_small",
        "score_too_high",
        "vague_scope",
    }
)

VALID_SCORE_DIRECTIONS = frozenset({"too_high", "too_low", "about_right"})


def _as_tag_list(raw: Any, allowed: frozenset[str]) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if s in allowed:
            out.append(s)
    return out


def normalize_survey_payload(
    *,
    fit_rating: int,
    score_accurate: bool | None,
    score_direction: str | None,
    good_tags: Any,
    bad_tags: Any,
) -> dict[str, Any]:
    if fit_rating < 1 or fit_rating > 5:
        raise ValueError("fit_rating must be 1–5")
    if score_direction is not None and score_direction not in VALID_SCORE_DIRECTIONS:
        raise ValueError(f"score_direction must be one of {sorted(VALID_SCORE_DIRECTIONS)}")
    return {
        "fit_rating": fit_rating,
        "score_accurate": score_accurate,
        "score_direction": score_direction,
        "good_tags": _as_tag_list(good_tags, GOOD_TAGS),
        "bad_tags": _as_tag_list(bad_tags, BAD_TAGS),
    }


def survey_row_to_rag_text(row: dict[str, Any]) -> str:
    """Single document for Chroma indexing."""
    nid = row.get("notice_id", "")
    agency = row.get("agency") or "unknown agency"
    title = (row.get("title") or "Untitled")[:200]
    fit = row.get("fit_rating")
    score = row.get("rule_score")
    direction = row.get("score_direction") or "unspecified"
    accurate = row.get("score_accurate")
    good = row.get("good_tags") or []
    bad = row.get("bad_tags") or []
    if isinstance(good, str):
        good = json.loads(good) if good.startswith("[") else []
    if isinstance(bad, str):
        bad = json.loads(bad) if bad.startswith("[") else []
    gn = (row.get("good_notes") or "").strip()
    bn = (row.get("bad_notes") or "").strip()
    ll = (row.get("lessons_learned") or "").strip()
    parts = [
        f"Fit feedback for SAM notice {nid} ({agency}).",
        f"Title: {title}.",
        f"Reviewer rated overall project fit {fit}/5 (1=poor fit for us, 5=strong fit).",
        f"Match rule_score at survey time: {score}.",
        f"Score direction (reviewer view): {direction}.",
    ]
    if accurate is not None:
        parts.append(f"Reviewer says score was accurate: {accurate}.")
    if good:
        parts.append("Good aspects: " + ", ".join(str(g) for g in good) + ".")
    if bad:
        parts.append("Bad aspects: " + ", ".join(str(b) for b in bad) + ".")
    if gn:
        parts.append(f"Good notes: {gn}")
    if bn:
        parts.append(f"Bad notes: {bn}")
    if ll:
        parts.append(f"Lesson learned: {ll}")
    parts.append(
        "Use this feedback when explaining scores and pass/bid advice; do not auto-change SQL weights."
    )
    return " ".join(parts)


def chunk_id_for_fit_survey(survey_id: int) -> str:
    """Stable Chroma document id for a single fit survey row."""
    import hashlib

    return hashlib.sha256(f"fit_survey:{survey_id}".encode()).hexdigest()[:24]
