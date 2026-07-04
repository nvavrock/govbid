#!/usr/bin/env python3
"""Load SAM bulk CSV from data/ into Postgres (bypasses n8n for large files)."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

from lib.match_profile import (  # noqa: E402
    MATCH_PROFILE,
    load_profile,
    should_ingest_row,
)
from lib.fit_profiles import sync_default_profile  # noqa: E402
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


def norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (key or "").lower())


def pick(row: dict, *keys: str) -> str | None:
    mapped = {norm_key(k): v for k, v in row.items()}
    for key in keys:
        val = mapped.get(norm_key(key))
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip()[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_ts(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def latest_csv() -> Path:
    files = sorted(DATA_DIR.glob("ContractOpportunitiesFull_*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV in {DATA_DIR}. Run: ./run_download.sh")
    return files[-1]


def main() -> int:
    load_env()
    profile = load_profile()
    csv_path = latest_csv()
    print(f"Using match profile: {MATCH_PROFILE} (ingest_mode={profile['ingest_mode']})")

    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("POSTGRES_PASSWORD not set in .env", file=sys.stderr)
        return 1

    conn = psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5433")),
        user=os.environ.get("POSTGRES_USER", "govbid"),
        password=password,
        dbname=os.environ.get("POSTGRES_DB", "govbid"),
    )

    inserted = 0
    processed = 0
    batch: list[tuple] = []

    upsert_sql = """
        INSERT INTO opportunities (
            notice_id, source, solicitation_number, title, posted_date,
            response_deadline, naics, psc, set_aside, set_aside_code,
            procurement_type, agency, office, state_code, place_of_performance,
            work_mode, ui_link, description_url, active, raw_data
        ) VALUES (
            %s, 'federal:sam', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, TRUE, %s::jsonb
        )
        ON CONFLICT (notice_id, source) DO UPDATE SET
            title = EXCLUDED.title,
            posted_date = EXCLUDED.posted_date,
            response_deadline = EXCLUDED.response_deadline,
            naics = EXCLUDED.naics,
            psc = EXCLUDED.psc,
            set_aside = EXCLUDED.set_aside,
            agency = EXCLUDED.agency,
            state_code = EXCLUDED.state_code,
            place_of_performance = EXCLUDED.place_of_performance,
            work_mode = EXCLUDED.work_mode,
            ui_link = EXCLUDED.ui_link,
            updated_at = NOW()
    """

    refresh_sql = """
        SELECT refresh_match_scores(%s, %s, %s, %s, %s)
    """
    refresh_args = (
        profile["naics_codes"],
        profile["psc_prefixes"],
        profile["include_keywords"],
        profile["exclude_keywords"],
        profile["exclude_set_asides"],
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingest_runs (source, status, metadata) "
                "VALUES ('federal:sam:bulk', 'running', '{\"script\":\"ingest_sam_csv.py\"}'::jsonb) "
                "RETURNING id"
            )
            run_id = cur.fetchone()[0]
            conn.commit()

            with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    processed += 1
                    notice_id = pick(row, "NoticeId", "Notice ID")
                    if not notice_id:
                        continue
                    title = pick(row, "Title")
                    naics = pick(row, "NaicsCode", "NAICS Code")
                    psc = pick(row, "ClassificationCode", "PSC")
                    active = pick(row, "Active")
                    if not should_ingest_row(
                        notice_id=notice_id,
                        naics=naics,
                        psc=psc,
                        title=title,
                        active=active,
                        profile=profile,
                    ):
                        continue

                    ui_link = pick(row, "Link", "uiLink") or (
                        f"https://sam.gov/opp/{notice_id}/view"
                    )
                    state = state_code_from_row(row)
                    pop = place_of_performance_from_row(row)
                    description = pick(row, "Description")
                    work_mode = classify_work_mode(
                        title=title,
                        description=description,
                        state_code=state,
                    )
                    batch.append((
                        notice_id,
                        pick(row, "Sol#", "SolicitationNumber"),
                        title,
                        parse_date(pick(row, "PostedDate", "Posted Date")),
                        parse_ts(pick(row, "ResponseDeadLine", "Response Deadline")),
                        naics,
                        psc,
                        pick(row, "SetASide", "Set Aside"),
                        pick(row, "SetASideCode", "SetAsideCode"),
                        pick(row, "Type", "Notice Type"),
                        pick(row, "Department/Ind.Agency", "Department", "Agency"),
                        pick(row, "Office", "Sub-Tier"),
                        state,
                        pop,
                        work_mode,
                        ui_link,
                        description,
                        json.dumps(row, default=str),
                    ))

                    if len(batch) >= 500:
                        cur.executemany(upsert_sql, batch)
                        inserted += len(batch)
                        batch.clear()
                        if processed % 100000 == 0:
                            print(f"  processed {processed:,} rows, matched {inserted:,}...")
                            conn.commit()

            if batch:
                cur.executemany(upsert_sql, batch)
                inserted += len(batch)

            sync_default_profile(conn)
            cur.execute(refresh_sql, refresh_args)
            scored = cur.fetchone()[0]

            cur.execute(
                "UPDATE ingest_runs SET status = 'success', finished_at = NOW(), "
                "rows_processed = %s, rows_inserted = %s WHERE id = %s",
                (processed, inserted, run_id),
            )
            conn.commit()

        print(f"Done: processed {processed:,} rows, upserted {inserted:,} opportunities, scored {scored:,}")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"Ingest failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
