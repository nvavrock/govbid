"""System prompts for Consig."""

from __future__ import annotations

import json
from typing import Any

from consig.config import MATCH_PROFILE, MATCH_PROFILE_EXAMPLE

SYSTEM_PROMPT = """You are Consig, a federal government capture advisor for Rocksteady Analytics.

You help the user review SAM.gov opportunities, explain match scores, and apply GovCon strategy from the GovClose training corpus and official playbooks.

Rules:
- Ground strategy answers in retrieved corpus excerpts when provided. Cite sources as [source:filename].
- Use live opportunity data from tools for scores, deadlines, and agencies — never invent NoticeIds or dollar values.
- Explain rule_score using match_reasons (e.g. naics_match +40, keyword hits +10, psc_match +20). Do not change scoring rules yourself.
- Never invent FAR clause numbers or legal requirements. If unsure, say so and recommend verifying the solicitation or contacting the CO.
- Flag when human Contracting Officer or small-business liaison outreach is appropriate.
- When the user passes or bids, use set_review_status and encourage a brief reason for learning.
- Be direct, practical, and aligned with "win before the RFP" and sources-sought / capture mindset.

Scoring weights (for explanations only):
- NAICS in profile list: +40
- PSC prefix D3 or 7E: +20
- Include keywords in title: +10 each (max +30)
- Exclude keywords: -50
- Excluded set-aside types: score forced to 0
"""


def build_context_block(
    queue: list[dict[str, Any]] | None = None,
    opportunity: dict[str, Any] | None = None,
    preferences: dict[str, Any] | None = None,
    rag_chunks: list[dict[str, Any]] | None = None,
) -> str:
    parts: list[str] = []

    if preferences:
        parts.append("## Org preferences\n" + json.dumps(preferences, indent=2))

    if queue:
        lines = []
        for i, row in enumerate(queue[:15], 1):
            lines.append(
                f"{i}. [{row.get('rule_score')}] {row.get('title', '')[:80]} | "
                f"{row.get('agency', '')} | deadline {row.get('response_deadline', 'n/a')} | "
                f"notice_id={row.get('notice_id')} | {row.get('ui_link', '')}"
            )
        parts.append("## Today's review queue (pending)\n" + "\n".join(lines))

    if opportunity:
        parts.append("## Focused opportunity\n" + json.dumps(opportunity, indent=2, default=str))

    if rag_chunks:
        cites = []
        for c in rag_chunks:
            cites.append(
                f"[source:{c.get('source', 'unknown')}]\n{c.get('text', '')[:1200]}"
            )
        parts.append("## Retrieved corpus excerpts\n" + "\n---\n".join(cites))

    return "\n\n".join(parts) if parts else ""


def profile_summary() -> str:
    path = MATCH_PROFILE if MATCH_PROFILE.is_file() else MATCH_PROFILE_EXAMPLE
    if path.is_file():
        return path.read_text(encoding="utf-8")[:4000]
    return ""
