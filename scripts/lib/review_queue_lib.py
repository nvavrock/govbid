"""Profile-driven review queue query (shared by CLI, verify, Counsel, digest)."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.match_profile import load_profile  # noqa: E402
from lib.fit_profiles import load_default_geography, load_profile_geography  # noqa: E402

REVIEW_QUEUE_SQL = """
WITH params AS (
    SELECT %(days_ahead)s::int AS days_ahead,
           %(min_score)s::int AS min_score,
           %(top_n)s::int AS top_n,
           %(require_match_reasons)s::boolean AS require_match_reasons,
           %(fit_bands)s::text[] AS fit_bands,
           %(home_states)s::text[] AS home_states,
           %(include_remote)s::boolean AS include_remote,
           %(include_unknown_location)s::boolean AS include_unknown_location
)
SELECT
    o.notice_id,
    o.solicitation_number,
    o.title,
    o.agency,
    o.naics,
    o.psc,
    o.set_aside,
    o.state_code,
    o.place_of_performance,
    o.work_mode,
    o.posted_date,
    o.response_deadline,
    o.ui_link,
    o.description_url,
    o.procurement_type,
    m.rule_score,
    m.match_reasons,
    m.fit_band,
    m.review_status,
    m.notes,
    (
        SELECT COUNT(*)
        FROM award_enrichment ae
        WHERE ae.naics_code = o.naics
          AND ae.awarding_agency = o.agency
    ) AS related_awards_count
FROM opportunities o
JOIN match_scores m ON m.opportunity_id = o.id
CROSS JOIN params p
WHERE o.active = TRUE
  AND o.source LIKE 'federal:%%'
  AND m.review_status = 'pending'
  AND m.rule_score >= p.min_score
  AND (
      p.fit_bands IS NULL
      OR COALESCE(m.fit_band, 'none') = ANY (p.fit_bands)
  )
  AND (
      cardinality(p.home_states) = 0
      OR o.state_code = ANY (p.home_states)
      OR (p.include_remote AND COALESCE(o.work_mode, 'unknown') = 'remote')
      OR (p.include_unknown_location AND COALESCE(o.work_mode, 'unknown') = 'unknown')
  )
  AND (
      NOT p.require_match_reasons
      OR (
          jsonb_array_length(COALESCE(m.match_reasons, '[]'::jsonb)) > 0
          AND COALESCE(m.fit_band, 'none') <> 'none'
      )
  )
  AND (
      o.response_deadline IS NULL
      OR o.response_deadline >= NOW()
  )
  AND (
      o.response_deadline IS NULL
      OR o.response_deadline <= NOW() + (p.days_ahead || ' days')::INTERVAL
  )
ORDER BY
    CASE COALESCE(m.fit_band, 'none')
        WHEN 'strong' THEN 1
        WHEN 'good' THEN 2
        WHEN 'stretch' THEN 3
        ELSE 4
    END,
    m.rule_score DESC,
    o.response_deadline ASC NULLS LAST
LIMIT (SELECT top_n FROM params);
"""

SHORTLIST_SQL = """
SELECT
    o.notice_id,
    o.solicitation_number,
    o.title,
    o.agency,
    o.naics,
    o.psc,
    o.set_aside,
    o.posted_date,
    o.response_deadline,
    o.ui_link,
    o.description_url,
    o.procurement_type,
    m.rule_score,
    m.match_reasons,
    m.review_status,
    m.notes,
    m.reviewed_at
FROM opportunities o
JOIN match_scores m ON m.opportunity_id = o.id
WHERE o.active = TRUE
  AND o.source LIKE 'federal:%%'
  AND m.review_status IN ('reviewing', 'bid')
ORDER BY m.reviewed_at DESC NULLS LAST, m.rule_score DESC
LIMIT %(limit)s;
"""

LIST_OPPORTUNITIES_SQL = """
SELECT
    o.notice_id,
    o.solicitation_number,
    o.title,
    o.agency,
    o.naics,
    o.psc,
    o.set_aside,
    o.posted_date,
    o.response_deadline,
    o.ui_link,
    o.description_url,
    o.procurement_type,
    m.rule_score,
    m.match_reasons,
    m.review_status,
    m.notes,
    m.reviewed_at
FROM opportunities o
JOIN match_scores m ON m.opportunity_id = o.id
WHERE o.active = TRUE
  AND o.source LIKE 'federal:%%'
  AND (%(status)s::text IS NULL OR m.review_status = %(status)s)
  AND m.rule_score >= %(min_score)s
  AND (%(agency_ilike)s::text IS NULL OR o.agency ILIKE %(agency_ilike)s)
  AND (%(naics)s::text IS NULL OR o.naics = %(naics)s)
  AND (
      %(days_ahead)s::int IS NULL
      OR o.response_deadline IS NULL
      OR o.response_deadline >= NOW()
  )
  AND (
      %(days_ahead)s::int IS NULL
      OR o.response_deadline IS NULL
      OR o.response_deadline <= NOW() + (%(days_ahead)s::int * INTERVAL '1 day')
  )
ORDER BY m.rule_score DESC, o.response_deadline ASC NULLS LAST
LIMIT %(limit)s OFFSET %(offset)s;
"""

COUNT_BY_STATUS_SQL = """
SELECT m.review_status, COUNT(*)::int AS cnt
FROM opportunities o
JOIN match_scores m ON m.opportunity_id = o.id
WHERE o.active = TRUE AND o.source LIKE 'federal:%%'
GROUP BY m.review_status
ORDER BY m.review_status;
"""


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def connect_params() -> dict[str, Any]:
    _load_env()
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD not set in .env")
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5433")),
        "user": os.environ.get("POSTGRES_USER", "govbid"),
        "password": password,
        "dbname": os.environ.get("POSTGRES_DB", "govbid"),
    }


DEFAULT_FIT_BANDS = ("strong", "good", "stretch")


def get_review_queue(
    *,
    days_ahead: int | None = None,
    min_score: int | None = None,
    top_n: int | None = None,
    fit_bands: list[str] | None = None,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    review = load_profile()["review"]
    if profile_id is not None:
        geo = load_profile_geography(profile_id)
    else:
        geo = load_default_geography()
    home_states = [s.strip().upper() for s in geo.get("home_states") or [] if s and str(s).strip()]
    include_remote = bool(geo.get("include_remote", True))
    include_unknown_location = bool(geo.get("include_unknown_location", False))
    bands = fit_bands if fit_bands is not None else list(DEFAULT_FIT_BANDS)
    params = {
        "days_ahead": days_ahead if days_ahead is not None else review["days_ahead"],
        "min_score": min_score if min_score is not None else review["min_score"],
        "top_n": top_n if top_n is not None else review["top_n"],
        "require_match_reasons": review.get("require_match_reasons", True),
        "fit_bands": bands or None,
        "home_states": home_states or None,
        "include_remote": include_remote,
        "include_unknown_location": include_unknown_location,
    }
    with psycopg.connect(**connect_params(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(REVIEW_QUEUE_SQL, params)
            return list(cur.fetchall())


def get_shortlist(*, limit: int = 50) -> list[dict[str, Any]]:
    with psycopg.connect(**connect_params(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(SHORTLIST_SQL, {"limit": limit})
            return list(cur.fetchall())


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
    review = load_profile()["review"]
    params = {
        "status": status,
        "min_score": min_score if min_score is not None else review["min_score"],
        "days_ahead": days_ahead,
        "agency_ilike": f"%{agency_ilike}%" if agency_ilike else None,
        "naics": naics,
        "limit": limit,
        "offset": offset,
    }
    with psycopg.connect(**connect_params(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(LIST_OPPORTUNITIES_SQL, params)
            return list(cur.fetchall())


def count_by_review_status() -> dict[str, int]:
    with psycopg.connect(**connect_params(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(COUNT_BY_STATUS_SQL)
            rows = cur.fetchall()
    return {r["review_status"]: r["cnt"] for r in rows}


def count_review_queue() -> int:
    return len(get_review_queue())
