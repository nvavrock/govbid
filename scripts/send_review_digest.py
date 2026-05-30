#!/usr/bin/env python3
"""Send daily review queue digest to Slack (profile-driven queue)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.match_profile import load_profile  # noqa: E402
from lib.review_queue_lib import get_review_queue  # noqa: E402


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


def _format_reasons(val: Any) -> str:
    if isinstance(val, list):
        return ", ".join(str(x) for x in val[:4])
    return str(val) if val else ""


def build_slack_payload(rows: list[dict[str, Any]], *, top_n: int) -> dict[str, Any]:
    today = date.today().isoformat()
    review = load_profile()["review"]
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    header = (
        f"*GovBid review digest* — {today}\n"
        f"{len(rows)} opportunities (min_score={review['min_score']}, "
        f"days_ahead={review['days_ahead']}, showing up to {top_n})"
    )
    if openai_key:
        header += "\n\nAfter you mark pass/bid in Consig, complete the Fit survey to improve grading for the next run."
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "divider"},
    ]
    for i, row in enumerate(rows[:top_n], 1):
        title = (row.get("title") or "Untitled")[:120]
        score = row.get("rule_score", "?")
        agency = row.get("agency") or "N/A"
        deadline = row.get("response_deadline")
        deadline_s = str(deadline)[:10] if deadline else "N/A"
        link = row.get("ui_link") or ""
        reasons = _format_reasons(row.get("match_reasons"))
        text = (
            f"*{i}. [{score}] {title}*\n"
            f"{agency} | deadline {deadline_s}\n"
            f"_{reasons}_\n"
        )
        if link:
            text += f"<{link}|SAM.gov>"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
    if not rows:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No opportunities matched filters today._",
                },
            }
        )
    return {"blocks": blocks}


def send_slack(payload: dict[str, Any], webhook_url: str) -> None:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(webhook_url, json=payload)
        r.raise_for_status()
        body = r.text.strip()
        if body and body != "ok":
            raise RuntimeError(f"Slack webhook unexpected response: {body}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send review queue digest to Slack")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON payload only")
    parser.add_argument("--send", action="store_true", help="POST to SLACK_WEBHOOK_URL")
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Max rows in message (default: DIGEST_TOP_N or profile top_n)",
    )
    args = parser.parse_args()

    _load_env()
    review = load_profile()["review"]
    top_n = args.top_n
    if top_n is None:
        top_n = int(os.environ.get("DIGEST_TOP_N", review["top_n"]))

    rows = get_review_queue(top_n=top_n)
    payload = build_slack_payload(rows, top_n=top_n)

    if args.dry_run or not args.send:
        print(json.dumps(payload, indent=2))
        if not args.send:
            print(f"\n(dry-run: {len(rows)} queue rows, use --send to post to Slack)")
        return 0

    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        print("SLACK_WEBHOOK_URL not set in .env", file=sys.stderr)
        return 1

    send_slack(payload, webhook)
    print(f"Sent digest with {min(len(rows), top_n)} opportunities to Slack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
