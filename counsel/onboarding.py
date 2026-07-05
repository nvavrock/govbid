"""First-run landing: demo profile or company setup wizard."""

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
    DEMO_BANNER,
    GLOSSARY_SOLICITATION,
    LANDING_DEMO_BODY,
    LANDING_DEMO_TITLE,
    LANDING_HEADLINE,
    LANDING_SETUP_BODY,
    LANDING_SETUP_TITLE,
    LANDING_SUBHEAD,
    ONBOARDING_STEPS,
    render_field_label,
    render_required_legend,
)
from lib.geography import US_STATE_CODES

US_STATE_OPTIONS = sorted(US_STATE_CODES)


def skip_onboarding() -> bool:
    return os.environ.get("COUNSEL_SKIP_ONBOARDING", "").strip() == "1"


def init_onboarding_state() -> None:
    defaults = {
        "onboarding_complete": False,
        "viewing_demo": False,
        "setup_mode": False,
        "forced_profile_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def should_show_landing() -> bool:
    if skip_onboarding():
        return False
    if st.session_state.onboarding_complete:
        return False
    if st.session_state.setup_mode:
        return False
    return True


def should_show_setup_wizard() -> bool:
    if skip_onboarding():
        return False
    return bool(st.session_state.setup_mode)


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


def activate_demo(db: Any) -> None:
    with st.spinner("Loading example matches…"):
        demo = db.ensure_demo_profile()
        db.refresh_scores_for_profile(demo["id"])
    st.session_state.viewing_demo = True
    st.session_state.setup_mode = False
    st.session_state.onboarding_complete = True
    st.session_state.forced_profile_id = demo["id"]
    st.session_state.onboarding_seen = True


def start_setup() -> None:
    st.session_state.setup_mode = True
    st.session_state.viewing_demo = False
    st.session_state.forced_profile_id = None


def finish_setup(profile_id: int) -> None:
    st.session_state.viewing_demo = False
    st.session_state.setup_mode = False
    st.session_state.onboarding_complete = True
    st.session_state.forced_profile_id = profile_id
    st.session_state.onboarding_seen = True
    if "fit_profile_active_id" in st.session_state:
        del st.session_state["fit_profile_active_id"]


def render_landing(db: Any) -> None:
    st.markdown(f"## {LANDING_HEADLINE}")
    st.markdown(LANDING_SUBHEAD)
    st.caption(GLOSSARY_SOLICITATION)

    col_demo, col_setup = st.columns(2)
    with col_demo:
        st.markdown(f"### {LANDING_DEMO_TITLE}")
        st.markdown(LANDING_DEMO_BODY)
        if st.button("Explore example", type="primary", key="landing_demo"):
            activate_demo(db)
            st.rerun()

    with col_setup:
        st.markdown(f"### {LANDING_SETUP_TITLE}")
        st.markdown(LANDING_SETUP_BODY)
        if st.button("Set up my company", key="landing_setup"):
            start_setup()
            st.rerun()

    with st.expander("How Counsel works", expanded=False):
        for i, step in enumerate(ONBOARDING_STEPS, 1):
            st.markdown(f"{i}. {step}")


def render_setup_wizard(db: Any, naics_picker: Any) -> None:
    st.markdown("## Set up your company")
    st.caption(
        "We use this to rank federal solicitations from SAM.gov. "
        "You can change everything later under **Your company profile**."
    )
    render_required_legend()

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
        col_back, col_submit = st.columns([1, 2])
        with col_back:
            back = st.form_submit_button("← Back")
        with col_submit:
            submit = st.form_submit_button("Show my matches", type="primary")

    if back:
        st.session_state.setup_mode = False
        st.rerun()

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


def render_demo_banner() -> None:
    st.info(DEMO_BANNER)
    if st.button("Set up my company", key="demo_banner_setup"):
        start_setup()
        st.rerun()


def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]
