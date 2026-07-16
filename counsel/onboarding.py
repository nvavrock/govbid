"""First-run company setup wizard."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from counsel.display import (
    GLOSSARY_SOLICITATION,
    ONBOARDING_STEPS,
    WIZARD_HEADLINE,
    WIZARD_SUBHEAD,
    render_field_label,
    render_required_legend,
)
from lib.geography import US_STATE_CODES

US_STATE_OPTIONS = sorted(US_STATE_CODES)


def skip_onboarding() -> bool:
    """Personal/operator installs skip the wizard by default.

    Set COUNSEL_SKIP_ONBOARDING=0 to force the first-run setup wizard.
    """
    raw = os.environ.get("COUNSEL_SKIP_ONBOARDING", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def init_onboarding_state() -> None:
    defaults = {
        "onboarding_complete": False,
        "forced_profile_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def should_show_setup_wizard() -> bool:
    if skip_onboarding():
        return False
    return not st.session_state.onboarding_complete


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "my-company"


def _unique_slug(base: str, db: Any) -> str:
    slug = base
    n = 2
    while db.get_fit_profile_by_slug(slug):
        slug = f"{base}-{n}"
        n += 1
    return slug


def finish_setup(profile_id: int) -> None:
    st.session_state.onboarding_complete = True
    st.session_state.forced_profile_id = profile_id
    st.session_state.onboarding_seen = True
    if "fit_profile_active_id" in st.session_state:
        del st.session_state["fit_profile_active_id"]


def render_setup_wizard(db: Any, naics_picker: Any) -> None:
    st.markdown(f"## {WIZARD_HEADLINE}")
    st.markdown(WIZARD_SUBHEAD)
    st.caption(GLOSSARY_SOLICITATION)
    render_required_legend()

    with st.expander("How Counsel works", expanded=False):
        for i, step in enumerate(ONBOARDING_STEPS, 1):
            st.markdown(f"{i}. {step}")

    if "setup_naics_draft" not in st.session_state:
        st.session_state.setup_naics_draft = []

    render_field_label("What types of work do you pursue? (NAICS)", required=True)
    st.caption("Pick at least one industry code below, or add keywords in the form.")
    with st.expander("Browse NAICS codes", expanded=True):
        merged = naics_picker(
            key_prefix="setup_naics",
            selected_codes=st.session_state.setup_naics_draft,
        )
        if merged != st.session_state.setup_naics_draft:
            st.session_state.setup_naics_draft = merged

    with st.form("setup_wizard_form"):
        render_field_label("Company name", required=True)
        name = st.text_input(
            "Company name",
            placeholder="Acme Services LLC",
            label_visibility="collapsed",
        )
        home_states = st.multiselect(
            "Home state(s) — where your team can work on-site",
            US_STATE_OPTIONS,
            help="Leave empty to show all U.S. locations. Remote opportunities can still appear below.",
        )
        include_remote = st.checkbox(
            "Include remote / nationwide opportunities",
            value=True,
        )
        keywords = st.text_area(
            "Words that describe your work (one per line)",
            placeholder="software\ncloud migration\ncybersecurity",
            height=100,
            help="Use if you did not pick any NAICS codes above.",
        )
        submit = st.form_submit_button("Show my matches", type="primary")

    if not submit:
        return

    clean_name = name.strip()
    if not clean_name:
        st.error("Enter your company name to continue.")
        return

    naics_codes = list(st.session_state.setup_naics_draft)
    if not naics_codes and not _lines_to_list(keywords):
        st.error("Pick at least one industry code or add a keyword describing your work.")
        return

    slug = _unique_slug(_slugify(clean_name), db)
    keyword_list = _lines_to_list(keywords)
    payload = {
        "slug": slug,
        "name": clean_name,
        "naics_codes": naics_codes,
        "include_keywords": keyword_list,
        "home_states": home_states,
        "include_remote": include_remote,
        "include_unknown_location": False,
        "is_default": True,
    }
    try:
        with st.spinner("Saving your profile and ranking opportunities…"):
            created = db.create_fit_profile(**payload)
            db.refresh_scores_for_profile(created["id"])
        finish_setup(created["id"])
        st.success("Profile saved. Here are your first matches.")
        st.rerun()
    except Exception as exc:
        st.error(f"Setup failed: {exc}")


def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]
