"""Postgres access for review queue, opportunities, and Counsel sessions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

import sys
from pathlib import Path

from counsel.config import QUERIES_DIR, postgres_params, review_defaults

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
    fit_bands: list[str] | None = None,
) -> list[dict[str, Any]]:
    from lib.review_queue_lib import get_review_queue as _lib_queue

    rows = _lib_queue(
        days_ahead=days_ahead,
        min_score=min_score,
        top_n=top_n,
        fit_bands=fit_bands,
    )
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


def list_distinct_naics(*, limit: int = 5000) -> list[str]:
    """All NAICS codes present in active federal opportunities."""
    sql = """
        SELECT DISTINCT o.naics
        FROM opportunities o
        WHERE o.active = TRUE
          AND o.source LIKE 'federal:%%'
          AND o.naics IS NOT NULL
          AND btrim(o.naics) <> ''
        ORDER BY o.naics
        LIMIT %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"limit": limit})
            rows = cur.fetchall()
    return [str(r["naics"]) for r in rows if r.get("naics")]


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


# --- Counsel session tables (003 migration) ---


def ensure_counsel_schema() -> None:
    """Apply 003_counsel.sql if counsel tables are missing."""
    migration = QUERIES_DIR.parent / "migrations" / "003_counsel.sql"
    if not migration.is_file():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'counsel_sessions'"
            )
            if cur.fetchone():
                return
        sql = migration.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def create_session(title: str | None = None) -> str:
    ensure_counsel_schema()
    session_id = str(uuid.uuid4())
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO counsel_sessions (id, title) VALUES (%s, %s)",
                (session_id, title or "Capture review"),
            )
        conn.commit()
    return session_id


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    ensure_counsel_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM counsel_sessions
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


def get_session_messages(session_id: str, limit: int = 40) -> list[dict[str, Any]]:
    ensure_counsel_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content, notice_id, created_at
                FROM counsel_messages
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
    ensure_counsel_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO counsel_messages (session_id, role, content, notice_id)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, role, content, notice_id),
            )
            cur.execute(
                "UPDATE counsel_sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
        conn.commit()


def get_preferences() -> dict[str, Any]:
    ensure_counsel_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM capture_preferences ORDER BY key")
            rows = cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_preference(key: str, value: Any) -> None:
    ensure_counsel_schema()
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
    ensure_counsel_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO counsel_feedback (notice_id, action, user_reason, helpful)
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
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'counsel_fit_surveys'"
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
    ensure_counsel_schema()
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
        INSERT INTO counsel_fit_surveys (
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
        FROM counsel_fit_surveys s
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
        FROM counsel_fit_surveys s
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
                "UPDATE counsel_fit_surveys SET indexed_at = NOW() WHERE id = %s",
                (survey_id,),
            )
        conn.commit()


def get_recent_fit_survey_summaries(*, limit: int = 10) -> list[str]:
    """Short lines for chat system context."""
    ensure_fit_surveys_schema()
    sql = """
        SELECT s.notice_id, s.fit_rating, s.rule_score, s.score_direction,
               s.good_tags, s.bad_tags, s.lessons_learned, o.title
        FROM counsel_fit_surveys s
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


# --- Fit profiles (006 migration) ---

_FIT_PROFILE_COLUMNS = """
    id, slug, name, capabilities,
    naics_codes, psc_prefixes, include_keywords,
    exclude_keywords, exclude_set_asides, eligible_set_asides,
    home_states, include_remote, include_unknown_location,
    weights, is_default, created_at, updated_at
"""


def _normalize_json_list(val: Any) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return [str(x) for x in parsed] if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return [x.strip() for x in val.splitlines() if x.strip()]
    return []


def _fit_profile_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    out = _serialize_row(row)
    for key in (
        "naics_codes",
        "psc_prefixes",
        "include_keywords",
        "exclude_keywords",
        "exclude_set_asides",
        "eligible_set_asides",
        "home_states",
        "weights",
    ):
        out[key] = _normalize_json_list(out.get(key))
    return out


def list_fit_profiles() -> list[dict[str, Any]]:
    sql = f"""
        SELECT {_FIT_PROFILE_COLUMNS}
        FROM fit_profiles
        ORDER BY is_default DESC, name ASC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [_fit_profile_row(r) for r in rows if r]


def get_fit_profile(profile_id: int) -> dict[str, Any] | None:
    sql = f"""
        SELECT {_FIT_PROFILE_COLUMNS}
        FROM fit_profiles
        WHERE id = %(id)s
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": profile_id})
            row = cur.fetchone()
    return _fit_profile_row(row)


def get_fit_profile_by_slug(slug: str) -> dict[str, Any] | None:
    sql = f"""
        SELECT {_FIT_PROFILE_COLUMNS}
        FROM fit_profiles
        WHERE slug = %(slug)s
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"slug": slug})
            row = cur.fetchone()
    return _fit_profile_row(row)


def get_default_fit_profile() -> dict[str, Any] | None:
    sql = f"""
        SELECT {_FIT_PROFILE_COLUMNS}
        FROM fit_profiles
        WHERE is_default = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    if row:
        return _fit_profile_row(row)
    profiles = list_fit_profiles()
    return profiles[0] if profiles else None


def create_fit_profile(
    *,
    slug: str,
    name: str,
    capabilities: str | None = None,
    naics_codes: list[str] | None = None,
    psc_prefixes: list[str] | None = None,
    include_keywords: list[str] | None = None,
    exclude_keywords: list[str] | None = None,
    exclude_set_asides: list[str] | None = None,
    eligible_set_asides: list[str] | None = None,
    home_states: list[str] | None = None,
    include_remote: bool = True,
    include_unknown_location: bool = False,
    is_default: bool = False,
) -> dict[str, Any]:
    slug = slug.strip()
    if not slug:
        raise ValueError("slug is required")
    sql = """
        INSERT INTO fit_profiles (
            slug, name, capabilities,
            naics_codes, psc_prefixes, include_keywords,
            exclude_keywords, exclude_set_asides, eligible_set_asides,
            home_states, include_remote, include_unknown_location,
            is_default
        ) VALUES (
            %(slug)s, %(name)s, %(capabilities)s,
            %(naics_codes)s::jsonb, %(psc_prefixes)s::jsonb, %(include_keywords)s::jsonb,
            %(exclude_keywords)s::jsonb, %(exclude_set_asides)s::jsonb, %(eligible_set_asides)s::jsonb,
            %(home_states)s::jsonb, %(include_remote)s, %(include_unknown_location)s,
            %(is_default)s
        )
        RETURNING id
    """
    params = {
        "slug": slug,
        "name": name.strip() or slug,
        "capabilities": capabilities,
        "naics_codes": json.dumps(naics_codes or []),
        "psc_prefixes": json.dumps(psc_prefixes or []),
        "include_keywords": json.dumps(include_keywords or []),
        "exclude_keywords": json.dumps(exclude_keywords or []),
        "exclude_set_asides": json.dumps(exclude_set_asides or []),
        "eligible_set_asides": json.dumps(eligible_set_asides or []),
        "home_states": json.dumps(home_states or []),
        "include_remote": include_remote,
        "include_unknown_location": include_unknown_location,
        "is_default": is_default,
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            if is_default:
                cur.execute("UPDATE fit_profiles SET is_default = FALSE WHERE is_default")
            cur.execute(sql, params)
            row = cur.fetchone()
            profile_id = int(row["id"])
        conn.commit()
    created = get_fit_profile(profile_id)
    if not created:
        raise RuntimeError("fit profile insert failed")
    return created


def update_fit_profile(
    profile_id: int,
    *,
    slug: str | None = None,
    name: str | None = None,
    capabilities: str | None = None,
    naics_codes: list[str] | None = None,
    psc_prefixes: list[str] | None = None,
    include_keywords: list[str] | None = None,
    exclude_keywords: list[str] | None = None,
    exclude_set_asides: list[str] | None = None,
    eligible_set_asides: list[str] | None = None,
    home_states: list[str] | None = None,
    include_remote: bool | None = None,
    include_unknown_location: bool | None = None,
    is_default: bool | None = None,
) -> dict[str, Any]:
    existing = get_fit_profile(profile_id)
    if not existing:
        raise LookupError(f"No fit profile id={profile_id}")

    fields: list[str] = []
    params: dict[str, Any] = {"id": profile_id}
    if slug is not None:
        fields.append("slug = %(slug)s")
        params["slug"] = slug.strip()
    if name is not None:
        fields.append("name = %(name)s")
        params["name"] = name.strip()
    if capabilities is not None:
        fields.append("capabilities = %(capabilities)s")
        params["capabilities"] = capabilities
    if naics_codes is not None:
        fields.append("naics_codes = %(naics_codes)s::jsonb")
        params["naics_codes"] = json.dumps(naics_codes)
    if psc_prefixes is not None:
        fields.append("psc_prefixes = %(psc_prefixes)s::jsonb")
        params["psc_prefixes"] = json.dumps(psc_prefixes)
    if include_keywords is not None:
        fields.append("include_keywords = %(include_keywords)s::jsonb")
        params["include_keywords"] = json.dumps(include_keywords)
    if exclude_keywords is not None:
        fields.append("exclude_keywords = %(exclude_keywords)s::jsonb")
        params["exclude_keywords"] = json.dumps(exclude_keywords)
    if exclude_set_asides is not None:
        fields.append("exclude_set_asides = %(exclude_set_asides)s::jsonb")
        params["exclude_set_asides"] = json.dumps(exclude_set_asides)
    if eligible_set_asides is not None:
        fields.append("eligible_set_asides = %(eligible_set_asides)s::jsonb")
        params["eligible_set_asides"] = json.dumps(eligible_set_asides)
    if home_states is not None:
        fields.append("home_states = %(home_states)s::jsonb")
        params["home_states"] = json.dumps([s.strip().upper() for s in home_states if s.strip()])
    if include_remote is not None:
        fields.append("include_remote = %(include_remote)s")
        params["include_remote"] = include_remote
    if include_unknown_location is not None:
        fields.append("include_unknown_location = %(include_unknown_location)s")
        params["include_unknown_location"] = include_unknown_location
    if is_default is not None:
        fields.append("is_default = %(is_default)s")
        params["is_default"] = is_default
    if not fields:
        return existing

    fields.append("updated_at = NOW()")
    sql = f"UPDATE fit_profiles SET {', '.join(fields)} WHERE id = %(id)s"
    with _connect() as conn:
        with conn.cursor() as cur:
            if is_default:
                cur.execute("UPDATE fit_profiles SET is_default = FALSE WHERE id <> %s", (profile_id,))
            cur.execute(sql, params)
        conn.commit()
    return get_fit_profile(profile_id) or existing


def delete_fit_profile(profile_id: int) -> None:
    existing = get_fit_profile(profile_id)
    if not existing:
        raise LookupError(f"No fit profile id={profile_id}")
    if existing.get("is_default"):
        raise ValueError("Cannot delete the default profile")
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fit_profiles WHERE id = %s", (profile_id,))
            if cur.rowcount == 0:
                raise LookupError(f"No fit profile id={profile_id}")
        conn.commit()


def refresh_scores_for_profile(profile_id: int | None = None) -> int:
    """Recompute match_scores using a fit_profiles row. Returns rows updated."""
    profile = get_fit_profile(profile_id) if profile_id else get_default_fit_profile()
    if not profile:
        raise LookupError("No fit profile found")
    sql = """
        SELECT refresh_match_scores(%s, %s, %s, %s, %s)
    """
    args = (
        profile["naics_codes"],
        profile["psc_prefixes"],
        profile["include_keywords"],
        profile["exclude_keywords"],
        profile["exclude_set_asides"],
    )
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
        conn.commit()
    if not row:
        return 0
    return int(list(row.values())[0])


def get_fit_survey_by_id(survey_id: int) -> dict[str, Any] | None:
    """Return a full fit survey row (including opportunity title/agency) for indexing and RAG context."""
    ensure_fit_surveys_schema()
    sql = """
        SELECT
            s.*,
            o.title,
            o.agency
        FROM counsel_fit_surveys s
        LEFT JOIN opportunities o ON o.notice_id = s.notice_id
        WHERE s.id = %s
        LIMIT 1;
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (survey_id,))
            row = cur.fetchone()
    return _serialize_row(row) if row else None
