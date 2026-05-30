#!/usr/bin/env python3
"""Download the public SAM.gov Contract Opportunities bulk CSV extract."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_URL = os.environ.get(
    "SAM_BULK_CSV_URL",
    "https://sam.gov/api/prod/fileextractservices/v1/api/download/"
    "Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv?privacy=Public",
)
DEFAULT_MIN_BYTES = 10_000_000  # ~10 MB floor; full extract is ~200+ MB
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 600
CHUNK_SIZE = 256 * 1024


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_session() -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET", "HEAD"],
    )
    session = requests.Session()
    session.headers["User-Agent"] = (
        "govbid/0.1 (+https://github.com/nvavrock/govbid; SAM.gov public bulk extract)"
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def cleanup_old_exports(target_dir: Path, keep_path: Path) -> None:
    keep_resolved = keep_path.resolve()
    for old_path in target_dir.glob("ContractOpportunitiesFull_*.csv"):
        if old_path.resolve() == keep_resolved:
            continue
        old_path.unlink()
        print(f"Removed old export: {old_path}")


def download_sam_opportunities(
    target_dir: Path,
    url: str,
    min_bytes: int,
) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    file_path = target_dir / f"ContractOpportunitiesFull_{date_str}.csv"
    tmp_path = file_path.with_suffix(".csv.part")

    if tmp_path.exists():
        tmp_path.unlink()

    print("Initiating download from SAM.gov...")
    session = build_session()
    total = 0

    try:
        with session.get(
            url,
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type.lower():
                raise ValueError(
                    "SAM.gov returned HTML instead of CSV; check SAM_BULK_CSV_URL"
                )

            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    total += len(chunk)

        if total < min_bytes:
            raise ValueError(
                f"Download too small ({total:,} bytes); expected at least {min_bytes:,}"
            )

        tmp_path.replace(file_path)
        print(f"Successfully archived: {file_path} ({total:,} bytes)")
        cleanup_old_exports(target_dir, file_path)
        return file_path
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=project_root() / "data",
        help="Directory for CSV output (default: <repo>/data)",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="SAM.gov bulk CSV URL (override with SAM_BULK_CSV_URL)",
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=int(os.environ.get("SAM_CSV_MIN_BYTES", DEFAULT_MIN_BYTES)),
        help="Minimum acceptable download size",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        download_sam_opportunities(args.data_dir, args.url, args.min_bytes)
    except requests.RequestException as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
