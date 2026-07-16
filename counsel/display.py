"""Plain-language display helpers for the Counsel Streamlit UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

# User-facing fit band labels
FIT_BAND_BADGES = {
    "strong": "Best match",
    "good": "Good match",
    "stretch": "Worth a look",
    "none": "Low fit",
}

FIT_BAND_OPTIONS = ["strong", "good", "stretch"]

MATCH_QUALITY_CHOICES = {
    "strong": "Best matches — strongest alignment with your profile",
    "good": "Good matches — solid fit, worth reviewing",
    "stretch": "Worth a look — possible fit, lower confidence",
}

WORK_MODE_LABELS = {
    "remote": "Remote / nationwide",
    "onsite": "On-site",
    "unknown": "Location not listed",
}

SHOW_ME_PRESETS = {
    "10 quick picks": 10,
    "25 standard (recommended)": 25,
    "50 deep dive": 50,
}

DEADLINE_PRESETS = {
    "Next 2 weeks": 14,
    "Next 30 days": 30,
    "Next 90 days": 90,
}

ACTION_LABELS = {
    "reviewing": "Save for review",
    "bid": "Pursuing",
    "pass": "Not for us",
    "pending": "Move back to today's list",
}

ACTION_HELP = {
    "reviewing": "Track this one — aim for 3–5 active pursuits at a time.",
    "bid": "You're committing capture effort; this becomes an active bid.",
    "pass": "Hide from today's list. Quick feedback afterward helps Counsel learn.",
    "pending": "Return this opportunity to today's matches.",
}

EMPTY_QUEUE_MESSAGE = (
    "No IT matches in this window. Widen Deadlines or Match quality, "
    "or refresh scores from the Profile tab after editing NAICS/keywords."
)

ONBOARDING_STEPS = [
    "We pull active federal solicitations from SAM.gov (updated daily).",
    "We rank them against your company profile — industry codes, keywords, location, and set-asides.",
    "You review a short list: save promising ones, pass on the rest.",
]

GLOSSARY_SOLICITATION = (
    "A *solicitation* is a government request for goods or services your company might bid on."
)

WIZARD_HEADLINE = "Set up your company"
WIZARD_SUBHEAD = (
    "Counsel pulls active solicitations from SAM.gov and ranks them against your industry, "
    "location, and keywords. Tell us about your business to see your first matches."
)

REQUIRED_MARK = '<span style="color:#ff4b4b;font-weight:700;">*</span>'


def render_field_label(label: str, *, required: bool = False) -> None:
    """Show a field label; append a red asterisk when the field is required."""
    suffix = f" {REQUIRED_MARK}" if required else ""
    st.markdown(f"{label}{suffix}", unsafe_allow_html=True)


def render_required_legend() -> None:
    st.markdown(f"{REQUIRED_MARK} Required", unsafe_allow_html=True)


def fit_band_badge(band: str | None) -> str:
    if not band:
        return FIT_BAND_BADGES["none"]
    return FIT_BAND_BADGES.get(str(band).lower(), str(band))


def work_mode_label(mode: str | None) -> str:
    if not mode:
        return WORK_MODE_LABELS["unknown"]
    return WORK_MODE_LABELS.get(str(mode).lower(), str(mode))


def humanize_deadline(value: Any) -> str:
    if value is None or value == "":
        return "No deadline listed"
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        text = str(value).strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return text
    now = datetime.now(timezone.utc)
    delta = (dt - now).days
    if delta < 0:
        return "Deadline passed"
    if delta == 0:
        return "Due today"
    if delta == 1:
        return "Due tomorrow"
    if delta <= 14:
        return f"Due in {delta} days"
    return dt.strftime("Due %b %d, %Y")


def _normalize_reasons(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                import json

                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except json.JSONDecodeError:
                pass
        return [text] if text else []
    return [str(raw)]


def explain_match_reason(reason: str) -> str:
    r = reason.strip()
    if r == "naics_match":
        return "Matches an industry code (NAICS) on your profile"
    if r == "psc_match":
        return "Matches a product/service code (PSC) on your profile"
    if r.startswith("keyword:"):
        kw = r.split(":", 1)[1]
        return f"Title mentions a keyword you care about: {kw}"
    if r.startswith("exclude:"):
        kw = r.split(":", 1)[1]
        return f"Title mentions something you exclude: {kw}"
    if r == "set_aside_excluded":
        return "Set-aside type you are not eligible to bid"
    return r.replace("_", " ").capitalize()


def explain_match_reasons(raw: Any, *, limit: int = 4) -> list[str]:
    reasons = _normalize_reasons(raw)
    out = [explain_match_reason(r) for r in reasons if r]
    return out[:limit]


def location_summary(row: dict[str, Any]) -> str:
    state = row.get("state_code")
    mode = row.get("work_mode")
    if mode == "remote":
        return "Remote / nationwide"
    if state:
        return f"{state} (on-site)"
    pop = row.get("place_of_performance")
    if pop:
        return str(pop)[:60]
    return work_mode_label(str(mode) if mode else None)


def context_summary(
    *,
    count: int,
    days_ahead: int,
    profile_name: str | None,
    home_states: list[str] | None,
    include_remote: bool,
) -> str:
    deadline = "next 2 weeks" if days_ahead <= 14 else f"next {days_ahead} days"
    geo_parts: list[str] = []
    if home_states:
        geo_parts.append(", ".join(home_states))
    if include_remote:
        geo_parts.append("remote work")
    geo = " + ".join(geo_parts) if geo_parts else "all locations"
    company = profile_name or "your company"
    return (
        f"Showing **{count}** opportunities due in the **{deadline}** "
        f"in **{geo}**, ranked by fit for **{company}**."
    )


def opportunity_card_label(row: dict[str, Any]) -> str:
    title = (row.get("title") or "Untitled").strip()
    if len(title) > 72:
        title = title[:69] + "..."
    band = fit_band_badge(row.get("fit_band"))
    return f"{band} · {title}"
