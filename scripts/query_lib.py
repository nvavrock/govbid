#!/usr/bin/env python3
"""Shared helpers for running db/queries/*.sql and printing CLI tables."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
QUERIES_DIR = ROOT / "db" / "queries"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def connect_params() -> dict[str, Any]:
    load_env()
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("Set POSTGRES_PASSWORD in .env", file=sys.stderr)
        sys.exit(1)
    return {
        "host": os.environ.get("POSTGRES_HOST") or os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT") or os.environ.get("PGPORT", "5432")),
        "user": os.environ.get("POSTGRES_USER", "govbid"),
        "password": password,
        "dbname": os.environ.get("POSTGRES_DB", "govbid"),
    }


def list_queries() -> list[str]:
    return sorted(p.stem for p in QUERIES_DIR.glob("*.sql"))


def load_sql(name: str) -> str:
    path = QUERIES_DIR / f"{name}.sql"
    if not path.is_file():
        print(f"Query not found: {path}", file=sys.stderr)
        print(f"Available: {', '.join(list_queries())}", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def format_cell(value: Any, max_width: int = 60) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str)
    else:
        text = str(value)
    if len(text) > max_width:
        return text[: max_width - 3] + "..."
    return text


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("(no rows)")
        return
    columns = list(rows[0].keys())
    formatted = [[format_cell(row.get(col)) for col in columns] for row in rows]
    widths = [len(col) for col in columns]
    for row in formatted:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def line(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    print(line(columns))
    print("-+-".join("-" * w for w in widths))
    for row in formatted:
        print(line(row))
    print(f"\n({len(rows)} row{'s' if len(rows) != 1 else ''})")


def run_query(name: str) -> None:
    sql = load_sql(name)
    params = connect_params()
    with psycopg.connect(**params, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                print("(ok — no result set)")
                return
            rows = cur.fetchall()
    print_table(rows)


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a saved SQL query against govbid Postgres.")
    parser.add_argument(
        "query",
        nargs="?",
        help=f"Query name without .sql ({', '.join(list_queries())})",
    )
    parser.add_argument("-l", "--list", action="store_true", help="List available queries")
    args = parser.parse_args(argv)
    if args.list:
        for name in list_queries():
            print(name)
        return
    if not args.query:
        parser.print_help(sys.stderr)
        sys.exit(1)
    run_query(args.query)


def main(name: str) -> None:
    run_query(name)


if __name__ == "__main__":
    cli()
