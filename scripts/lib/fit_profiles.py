"""Sync config/match-profile.yaml into fit_profiles (default row)."""

from __future__ import annotations

import json
import os
from typing import Any

import psycopg

from lib.match_profile import MATCH_PROFILE, load_profile, profile_meta


def connect_params() -> dict[str, Any]:
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD not set in .env")
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "user": os.environ.get("POSTGRES_USER", "govbid"),
        "password": password,
        "dbname": os.environ.get("POSTGRES_DB", "govbid"),
    }


def load_default_geography(conn: psycopg.Connection[Any] | None = None) -> dict[str, Any]:
    """Geography filter from default fit_profiles row, else match-profile.yaml."""
    sql = """
        SELECT home_states, include_remote, include_unknown_location
        FROM fit_profiles
        WHERE is_default = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
    """
    row = None
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    else:
        with psycopg.connect(**connect_params()) as c:
            with c.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
    if row:
        home = row[0]
        if isinstance(home, str):
            home = json.loads(home)
        return {
            "home_states": list(home or []),
            "include_remote": bool(row[1]),
            "include_unknown_location": bool(row[2]),
        }
    return load_profile().get("geography", {})


def sync_default_profile(conn: psycopg.Connection[Any] | None = None) -> int:
    """Upsert the default fit_profiles row from match-profile.yaml. Returns profile id."""
    meta = profile_meta()
    p = load_profile()
    geo = p.get("geography") or {}
    slug = meta.get("slug") or "default"
    name = meta.get("name") or "Default profile"

    sql = """
        INSERT INTO fit_profiles (
            slug, name, capabilities,
            naics_codes, psc_prefixes, include_keywords,
            exclude_keywords, exclude_set_asides,
            home_states, include_remote, include_unknown_location,
            is_default
        ) VALUES (
            %(slug)s, %(name)s, %(capabilities)s,
            %(naics_codes)s::jsonb, %(psc_prefixes)s::jsonb, %(include_keywords)s::jsonb,
            %(exclude_keywords)s::jsonb, %(exclude_set_asides)s::jsonb,
            %(home_states)s::jsonb, %(include_remote)s, %(include_unknown_location)s,
            TRUE
        )
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            capabilities = EXCLUDED.capabilities,
            naics_codes = EXCLUDED.naics_codes,
            psc_prefixes = EXCLUDED.psc_prefixes,
            include_keywords = EXCLUDED.include_keywords,
            exclude_keywords = EXCLUDED.exclude_keywords,
            exclude_set_asides = EXCLUDED.exclude_set_asides,
            is_default = TRUE,
            updated_at = NOW()
    """
    params = {
        "slug": slug,
        "name": name,
        "capabilities": meta.get("capabilities"),
        "naics_codes": json.dumps(p["naics_codes"]),
        "psc_prefixes": json.dumps(p["psc_prefixes"]),
        "include_keywords": json.dumps(p["include_keywords"]),
        "exclude_keywords": json.dumps(p["exclude_keywords"]),
        "exclude_set_asides": json.dumps(p["exclude_set_asides"]),
        "home_states": json.dumps(geo.get("home_states") or []),
        "include_remote": bool(geo.get("include_remote", True)),
        "include_unknown_location": bool(geo.get("include_unknown_location", False)),
    }

    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fit_profiles SET is_default = FALSE WHERE slug <> %s AND is_default",
                (slug,),
            )
            cur.execute(sql, params)
            cur.execute("SELECT id FROM fit_profiles WHERE slug = %s", (slug,))
            row = cur.fetchone()
            return int(row[0]) if row else 0

    with psycopg.connect(**connect_params()) as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE fit_profiles SET is_default = FALSE WHERE slug <> %s AND is_default",
                (slug,),
            )
            cur.execute(sql, params)
            cur.execute("SELECT id FROM fit_profiles WHERE slug = %s", (slug,))
            row = cur.fetchone()
        c.commit()
        return int(row[0]) if row else 0
