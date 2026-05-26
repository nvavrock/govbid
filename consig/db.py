"""Postgres access for review queue, opportunities, and Consig sessions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

import sys
from pathlib import Path

from consig.config import QUERIES_DIR, postgres_params, review_defaults

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

OPPORTUNITY_SQL = """
SELECT
    o.notice_id,
    o.solicitation_number,
    o.title,
    o.agency,
    o.office,
    o.naics,
    o.psc,
    o.set_aside,
    o.set_aside_code,
    o.posted_date,
    o.response_deadline,
    o.ui_link,
    o.description_url,
    o.procurement_type,
    o.id AS opportunity_id,
    m.rule_score,
    m.match_reasons,
    m.review_status,
    m.notes,
    m.reviewed_at
FROM opportunities o
JOIN match_scores m ON m.opportunity_id = o.id
WHERE o.notice_id = %(notice_id)s
LIMIT 1;
"""

VALID_REVIEW_STATUSES = frozenset({"pending", "reviewing", "bid", "pass", "expired"})


def _connect():
    return psycopg.connect(**postgres_params(), row_factory=dict_row)


def get_review_queue(
    *,
    days_ahead: int | None = None,
    min_score: int | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    from lib.review_queue_lib import get_review_queue as _lib_queue

    rows = _lib_queue(days_ahead=days_ahead, min_score=min_score, top_n=top_n)
    return [_serialize_row(r) for r in rows]


def get_shortlist(*, limit: int = 50) -> list[dict[str, Any]]:
    from lib.review_queue_lib import get_shortlist as _lib_shortlist

    return [_serialize_row(r) for r in _lib_shortlist(limit=limit)]


def list_opportunities(
    *,
    status: str | None = None,
    min_score: int | None = None,
    days_ahead: int | None = None,
    agency_ilike: str | None = None,
    naics: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    from lib.review_queue_lib import list_opportunities as _lib_list

    rows = _lib_list(
        status=status,
        min_score=min_score,
        days_ahead=days_ahead,
        agency_ilike=agency_ilike,
        naics=naics,
        limit=limit,
        offset=offset,
    )
    return [_serialize_row(r) for r in rows]


def count_by_review_status() -> dict[str, int]:
    from lib.review_queue_lib import count_by_review_status as _lib_count

    return _lib_count()


def get_opportunity(notice_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(OPPORTUNITY_SQL, {"notice_id": notice_id})
            row = cur.fetchone()
    return _serialize_row(row) if row else None


def set_review_status(
    notice_id: str,
    status: str,
    notes: str | None = None,
) -> dict[str, Any]:
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Invalid status {status!r}; use one of {sorted(VALID_REVIEW_STATUSES)}")
    sql = """
        UPDATE match_scores m
        SET review_status = %(status)s,
            notes = COALESCE(%(notes)s, m.notes),
            reviewed_at = NOW()
        FROM opportunities o
        WHERE m.opportunity_id = o.id
          AND o.notice_id = %(notice_id)s
        RETURNING o.notice_id, m.review_status, m.notes, m.reviewed_at;
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"notice_id": notice_id, "status": status, "notes": notes})
            row = cur.fetchone()
            if not row:
                raise LookupError(f"No opportunity found for notice_id={notice_id!r}")
        conn.commit()
    return _serialize_row(row)


def _serialize_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, (dict, list)):
            out[k] = v
        else:
            out[k] = v
    return out


# --- Consig session tables (003 migration) ---


def ensure_consig_schema() -> None:
    """Apply 003_consig.sql if tables are missing."""
    migration = QUERIES_DIR.parent / "migrations" / "003_consig.sql"
    if not migration.is_file():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'consig_sessions'"
            )
            if cur.fetchone():
                return
        sql = migration.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def create_session(title: str | None = None) -> str:
    ensure_consig_schema()
    session_id = str(uuid.uuid4())
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO consig_sessions (id, title) VALUES (%s, %s)",
                (session_id, title or "Capture review"),
            )
        conn.commit()
    return session_id


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    ensure_consig_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM consig_sessions
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


def get_session_messages(session_id: str, limit: int = 40) -> list[dict[str, Any]]:
    ensure_consig_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content, notice_id, created_at
                FROM consig_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


def append_message(
    session_id: str,
    role: str,
    content: str,
    notice_id: str | None = None,
) -> None:
    ensure_consig_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO consig_messages (session_id, role, content, notice_id)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, role, content, notice_id),
            )
            cur.execute(
                "UPDATE consig_sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
        conn.commit()


def get_preferences() -> dict[str, Any]:
    ensure_consig_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM capture_preferences ORDER BY key")
            rows = cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_preference(key: str, value: Any) -> None:
    ensure_consig_schema()
    if isinstance(value, (dict, list)):
        payload = json.dumps(value)
    elif isinstance(value, str) and value.startswith(("{", "[")):
        payload = value
    else:
        payload = json.dumps(value)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO capture_preferences (key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (key, payload),
            )
        conn.commit()


def record_feedback(
    notice_id: str,
    action: str,
    user_reason: str | None = None,
    helpful: bool | None = None,
) -> None:
    ensure_consig_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO consig_feedback (notice_id, action, user_reason, helpful)
                VALUES (%s, %s, %s, %s)
                """,
                (notice_id, action, user_reason, helpful),
            )
        conn.commit()


# --- Fit surveys (004 migration) ---


def ensure_fit_surveys_schema() -> None:
    """Apply 004_fit_surveys.sql if table is missing."""
    migration = QUERIES_DIR.parent / "migrations" / "004_fit_surveys.sql"
    if not migration.is_file():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'consig_fit_surveys'"
            )
            if cur.fetchone():
                return
        sql = migration.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def save_fit_survey(
    notice_id: str,
    review_status: str,
    *,
    fit_rating: int,
    rule_score: int | None = None,
    score_accurate: bool | None = None,
    score_direction: str | None = None,
    good_tags: list[str] | None = None,
    bad_tags: list[str] | None = None,
    good_notes: str | None = None,
    bad_notes: str | None = None,
    lessons_learned: str | None = None,
) -> dict[str, Any]:
    ensure_consig_schema()
    ensure_fit_surveys_schema()
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Invalid review_status {review_status!r}")
    opp = get_opportunity(notice_id)
    if not opp:
        raise LookupError(f"No opportunity for notice_id={notice_id!r}")
    opportunity_id = opp.get("opportunity_id")
    if rule_score is None:
        rule_score = opp.get("rule_score")
    sql = """
        INSERT INTO consig_fit_surveys (
            notice_id, opportunity_id, review_status, rule_score, fit_rating,
            score_accurate, score_direction, good_tags, bad_tags,
            good_notes, bad_notes, lessons_learned
        ) VALUES (
            %(notice_id)s, %(opportunity_id)s, %(review_status)s, %(rule_score)s, %(fit_rating)s,
            %(score_accurate)s, %(score_direction)s, %(good_tags)s::jsonb, %(bad_tags)s::jsonb,
            %(good_notes)s, %(bad_notes)s, %(lessons_learned)s
        )
        RETURNING id, notice_id, created_at
    """
    payload = {
        "notice_id": notice_id,
        "opportunity_id": opportunity_id,
        "review_status": review_status,
        "rule_score": rule_score,
        "fit_rating": fit_rating,
        "score_accurate": score_accurate,
        "score_direction": score_direction,
        "good_tags": json.dumps(good_tags or []),
        "bad_tags": json.dumps(bad_tags or []),
        "good_notes": good_notes,
        "bad_notes": bad_notes,
        "lessons_learned": lessons_learned,
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, payload)
            row = cur.fetchone()
        conn.commit()
    return _serialize_row(row) if row else {}


def list_fit_surveys(
    *, notice_id: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    ensure_fit_surveys_schema()
    where = "WHERE notice_id = %(notice_id)s" if notice_id else ""
    params: dict[str, Any] = {"limit": limit}
    if notice_id:
        params["notice_id"] = notice_id
    sql = f"""
        SELECT
            s.id,
            s.notice_id,
            s.opportunity_id,
            s.review_status,
            s.rule_score,
            s.fit_rating,
            s.score_accurate,
            s.score_direction,
            s.good_tags,
            s.bad_tags,
            s.good_notes,
            s.bad_notes,
            s.lessons_learned,
            s.indexed_at,
            s.created_at,
            o.title,
            o.agency
        FROM consig_fit_surveys s
        LEFT JOIN opportunities o ON o.notice_id = s.notice_id
        {where}
        ORDER BY s.created_at DESC
        LIMIT %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


def list_unindexed_fit_surveys() -> list[dict[str, Any]]:
    ensure_fit_surveys_schema()
    sql = """
        SELECT s.id, s.notice_id, s.review_status, s.rule_score, s.fit_rating,
               s.score_accurate, s.score_direction, s.good_tags, s.bad_tags,
               s.good_notes, s.bad_notes, s.lessons_learned, s.created_at,
               o.title, o.agency
        FROM consig_fit_surveys s
        LEFT JOIN opportunities o ON o.notice_id = s.notice_id
        WHERE s.indexed_at IS NULL
        ORDER BY s.id ASC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


def mark_fit_survey_indexed(survey_id: int) -> None:
    ensure_fit_surveys_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE consig_fit_surveys SET indexed_at = NOW() WHERE id = %s",
                (survey_id,),
            )
        conn.commit()


def get_recent_fit_survey_summaries(*, limit: int = 10) -> list[str]:
    """Short lines for chat system context."""
    ensure_fit_surveys_schema()
    sql = """
        SELECT s.notice_id, s.fit_rating, s.rule_score, s.score_direction,
               s.good_tags, s.bad_tags, s.lessons_learned, o.title
        FROM consig_fit_surveys s
        LEFT JOIN opportunities o ON o.notice_id = s.notice_id
        ORDER BY s.created_at DESC
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    lines: list[str] = []
    for r in rows:
        title = (r.get("title") or "")[:60]
        nid = r.get("notice_id", "")[:12]
        fit = r.get("fit_rating")
        sd = r.get("score_direction") or ""
        ll = (r.get("lessons_learned") or "")[:120]
        lines.append(
            f"notice {nid}… fit {fit}/5 score_dir={sd} — {title}"
            + (f" | lesson: {ll}" if ll else "")
        )
    return lines


def get_fit_survey_by_id(survey_id: int) -> dict[str, Any] | None:
    """Return a full fit survey row (including opportunity title/agency) for indexing and RAG context."""
    ensure_fit_surveys_schema()
    sql = """
        SELECT
            s.*,
            o.title,
            o.agency
        FROM consig_fit_surveys s
        LEFT JOIN opportunities o ON o.notice_id = s.notice_id
        WHERE s.id = %s
        LIMIT 1;
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (survey_id,))
            row = cur.fetchone()
    return _serialize_row(row) if row else None
