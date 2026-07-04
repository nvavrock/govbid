"""Streamlit UI for Counsel capture copilot and Phase 2 opportunity dashboard."""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from counsel.config import load_env, review_defaults  # noqa: E402
from counsel.branding import sanitize_user_facing  # noqa: E402
from counsel.survey_schema import (
    BAD_TAGS,
    GOOD_TAGS,
    chunk_id_for_fit_survey,
    normalize_survey_payload,
    survey_row_to_rag_text,
)

load_env()

API_URL = os.environ.get("COUNSEL_API_URL", "http://127.0.0.1:8000").rstrip("/")
USE_INPROCESS = os.environ.get("COUNSEL_INPROCESS", "1") == "1"

from lib.naics_lookup import (  # noqa: E402
    label_for_code,
    search_codes,
    sector_options,
    codes_for_sector,
)
from lib.geography import US_STATE_CODES  # noqa: E402

QUEUE_COLUMNS = [
    "fit_band",
    "title",
    "agency",
    "state_code",
    "work_mode",
    "posted_date",
    "response_deadline",
    "naics_label",
    "psc",
    "set_aside",
    "match_reasons",
    "notice_id",
    "ui_link",
]

US_STATE_OPTIONS = sorted(US_STATE_CODES)
WORK_MODE_LABELS = {"remote": "Remote", "onsite": "On-site", "unknown": "Location TBD"}

FIT_BAND_OPTIONS = ["strong", "good", "stretch"]
FIT_BAND_LABELS = {
    "strong": "Strong fit",
    "good": "Good fit",
    "stretch": "Stretch",
}


def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _list_to_lines(items: list[str] | None) -> str:
    return "\n".join(items or [])


def list_fit_profiles() -> list[dict]:
    if USE_INPROCESS:
        return _db().list_fit_profiles()
    return _api_get("/fit-profiles")


def save_fit_profile(profile_id: int, payload: dict) -> dict:
    if USE_INPROCESS:
        return _db().update_fit_profile(profile_id, **payload)
    with httpx.Client(timeout=180.0) as client:
        r = client.put(f"{API_URL}/fit-profiles/{profile_id}", json=payload)
        r.raise_for_status()
        return r.json()


def refresh_profile_scores(profile_id: int) -> int:
    if USE_INPROCESS:
        return _db().refresh_scores_for_profile(profile_id)
    result = _api_post(f"/fit-profiles/{profile_id}/refresh-scores", {})
    return int(result.get("rows_updated", 0))


@st.cache_data(ttl=300, show_spinner=False)
def fetch_distinct_naics() -> list[str]:
    if USE_INPROCESS:
        return _db().list_distinct_naics()
    return _api_get("/naics")


def _naics_selectbox(
    *,
    key: str,
    label: str = "NAICS",
    caption: str | None = None,
) -> str:
    """NAICS picker using 2022 Census sector structure + titles."""
    all_naics = set(fetch_distinct_naics())
    sectors = sector_options()
    sector_labels = {code: text for code, text in sectors}
    sector_codes = [""] + [code for code, _ in sectors]
    sector_pick = st.selectbox(
        "NAICS sector (2022 structure)",
        sector_codes,
        format_func=lambda c: "All sectors" if not c else sector_labels.get(c, c),
        key=f"{key}_sector",
    )
    search = st.text_input("Search NAICS code or title", key=f"{key}_search")
    if search.strip():
        options = search_codes(
            search,
            sector=sector_pick or None,
            in_database=all_naics,
            limit=100,
        )
    elif sector_pick:
        options = codes_for_sector(sector_pick, in_database=all_naics)
        options = options[:100]
    else:
        options = search_codes("", in_database=all_naics, limit=100)

    display = [("", "Any NAICS")] + options
    pick = st.selectbox(
        label,
        [code for code, _ in display],
        format_func=lambda c: next(l for code, l in display if code == c),
        key=key,
    )
    if caption:
        st.caption(caption)
    else:
        st.caption(
            f"{len(all_naics)} NAICS codes in your SAM data · "
            "Titles from Census 2022 NAICS structure."
        )
    return pick


def _naics_profile_picker(*, key_prefix: str, selected_codes: list[str]) -> list[str]:
    """Sector-based multiselect to add NAICS codes to a fit profile."""
    all_naics = set(fetch_distinct_naics())
    sectors = sector_options()
    sector_labels = {code: text for code, text in sectors}
    sector_pick = st.selectbox(
        "NAICS sector",
        [""] + [code for code, _ in sectors],
        format_func=lambda c: "Choose a sector…" if not c else sector_labels.get(c, c),
        key=f"{key_prefix}_sector",
    )
    search = st.text_input("Search within sector", key=f"{key_prefix}_search")
    if sector_pick:
        pool = codes_for_sector(sector_pick, in_database=all_naics)
    else:
        pool = search_codes(search or "", in_database=all_naics, limit=150)
    if search.strip() and sector_pick:
        q = search.strip().lower()
        pool = [(c, l) for c, l in pool if q in c or q in l.lower()]

    options = [c for c, _ in pool[:150]]
    picks = st.multiselect(
        "Add NAICS codes (with titles)",
        options,
        format_func=label_for_code,
        key=f"{key_prefix}_pick",
    )
    merged = sorted(set(selected_codes) | set(picks))
    if picks:
        st.caption(f"Selected {len(merged)} code(s) for your profile.")
    return merged


def _api_get(path: str, **params: Any) -> object:
    with httpx.Client(timeout=120.0) as client:
        r = client.get(f"{API_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


def _api_post(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=180.0) as client:
        r = client.post(f"{API_URL}{path}", json=payload)
        r.raise_for_status()
        return r.json()


def _chat_inprocess(
    message: str, session_id: str | None, notice_id: str | None, briefing: bool
) -> dict:
    from counsel import chat

    if briefing:
        return chat.daily_briefing(session_id=session_id)
    return chat.handle_chat(message, session_id=session_id, notice_id=notice_id)


def run_chat(
    message: str,
    session_id: str | None,
    notice_id: str | None,
    briefing: bool = False,
) -> dict:
    if USE_INPROCESS:
        return _chat_inprocess(message, session_id, notice_id, briefing)
    return _api_post(
        "/chat",
        {
            "session_id": session_id,
            "message": message,
            "notice_id": notice_id,
            "briefing": briefing,
        },
    )


def _db():
    from counsel import db

    return db


def fetch_queue(
    days_ahead: int | None,
    top_n: int | None,
    fit_bands: list[str] | None,
) -> list:
    if USE_INPROCESS:
        return _db().get_review_queue(
            days_ahead=days_ahead,
            top_n=top_n,
            fit_bands=fit_bands,
            min_score=0,
        )
    params: dict[str, Any] = {
        "days_ahead": days_ahead,
        "top_n": top_n,
        "min_score": 0,
    }
    if fit_bands:
        params["fit_bands"] = ",".join(fit_bands)
    return _api_get("/queue", **params)


def apply_review(notice_id: str, status: str, notes: str | None = None) -> None:
    if USE_INPROCESS:
        _db().set_review_status(notice_id, status, notes)
        _db().record_feedback(notice_id, status, notes)
        if status in ("pass", "bid"):
            st.session_state.fit_survey_notice_id = notice_id
    else:
        _api_post(
            "/review",
            {"notice_id": notice_id, "status": status, "notes": notes},
        )


def submit_fit_survey(
    notice_id: str,
    review_status: str,
    *,
    fit_rating: int,
    score_accurate: bool | None,
    score_direction: str | None,
    good_tags: list[str],
    bad_tags: list[str],
    good_notes: str | None,
    bad_notes: str | None,
    lessons_learned: str | None,
) -> bool:
    row = _db().save_fit_survey(
        notice_id,
        review_status,
        fit_rating=fit_rating,
        score_accurate=score_accurate,
        score_direction=score_direction,
        good_tags=good_tags,
        bad_tags=bad_tags,
        good_notes=good_notes,
        bad_notes=bad_notes,
        lessons_learned=lessons_learned,
    )
    survey_id = row.get("id")
    if not survey_id:
        return False

    # Index immediately for RAG.
    try:
        from counsel import rag

        fit_row = _db().get_fit_survey_by_id(int(survey_id))
        if fit_row:
            rag.index_chunks(
                [
                    {
                        "id": chunk_id_for_fit_survey(int(survey_id)),
                        "text": survey_row_to_rag_text(fit_row),
                        "source": f"fit_feedback/survey_{survey_id}",
                        "title": "fit_feedback",
                    }
                ],
                reset=False,
            )
            _db().mark_fit_survey_indexed(int(survey_id))
    except Exception:
        # Leave indexed_at NULL; batch index script can fill later.
        pass
    return True


def _format_reasons(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val)


def _rows_for_display(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        row = dict(r)
        row["match_reasons"] = _format_reasons(row.get("match_reasons"))
        naics = row.get("naics")
        row["naics_label"] = label_for_code(str(naics)) if naics else ""
        mode = row.get("work_mode")
        if mode:
            row["work_mode"] = WORK_MODE_LABELS.get(str(mode), str(mode))
        if row.get("title") and len(str(row["title"])) > 80:
            row["title"] = str(row["title"])[:77] + "..."
        out.append(row)
    return out


def _csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    keys = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        row = dict(r)
        if isinstance(row.get("match_reasons"), (list, dict)):
            row["match_reasons"] = json.dumps(row["match_reasons"])
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _review_buttons(notice_id: str, key_prefix: str, notes: str = "") -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Shortlist", key=f"{key_prefix}_reviewing"):
            apply_review(notice_id, "reviewing", notes or None)
            st.rerun()
    with c2:
        if st.button("Bid", key=f"{key_prefix}_bid"):
            apply_review(notice_id, "bid", notes or None)
            st.rerun()
    with c3:
        if st.button("Pass", key=f"{key_prefix}_pass"):
            apply_review(notice_id, "pass", notes or None)
            st.rerun()
    with c4:
        if st.button("Reset", key=f"{key_prefix}_pending"):
            apply_review(notice_id, "pending", notes or None)
            st.rerun()


def render_sidebar(defaults: dict) -> tuple[list[str], int, int, dict | None]:
    profiles: list[dict] = []
    active_profile: dict | None = None
    try:
        profiles = list_fit_profiles()
        active_profile = next((p for p in profiles if p.get("is_default")), None)
        if not active_profile and profiles:
            active_profile = profiles[0]
    except Exception as exc:
        st.sidebar.caption(f"Profiles unavailable: {exc}")

    with st.sidebar:
        st.subheader("Fit profile")
        if profiles:
            labels = {p["id"]: f"{p.get('name', p.get('slug', 'profile'))}" for p in profiles}
            default_id = active_profile["id"] if active_profile else profiles[0]["id"]
            selected_id = st.selectbox(
                "Active profile",
                options=list(labels.keys()),
                format_func=lambda pid: labels[pid],
                index=list(labels.keys()).index(default_id),
                key="active_profile_id",
            )
            active_profile = next(p for p in profiles if p["id"] == selected_id)
            st.caption(f"Slug: `{active_profile.get('slug', '')}`")
            home = active_profile.get("home_states") or []
            if home:
                st.caption(
                    f"Geography: {', '.join(home)}"
                    + (" + remote" if active_profile.get("include_remote", True) else "")
                )
            else:
                st.caption("Geography: all locations (set home states in My fit profile)")
        else:
            st.info("No fit profile yet — use the My fit profile tab.")

        st.divider()
        st.subheader("Best fits filters")
        fit_bands = st.multiselect(
            "Fit bands",
            FIT_BAND_OPTIONS,
            default=FIT_BAND_OPTIONS,
            format_func=lambda b: FIT_BAND_LABELS.get(b, b),
            key="filter_fit_bands",
        )
        days_ahead = st.slider(
            "Days ahead",
            7,
            90,
            int(defaults["days_ahead"]),
            key="filter_days_ahead",
        )
        top_n = st.slider(
            "Top N",
            5,
            50,
            int(defaults["top_n"]),
            key="filter_top_n",
        )
        st.caption("Ranked by fit band, then relevance — no min score gate.")

        try:
            counts = _db().count_by_review_status() if USE_INPROCESS else {}
            if counts:
                st.divider()
                st.subheader("Status counts")
                for status, cnt in sorted(counts.items()):
                    st.text(f"{status}: {cnt}")
        except Exception as exc:
            st.caption(f"Counts unavailable: {exc}")

        st.divider()
        st.subheader("Chat session")
        if st.button("New chat session"):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()
        if st.button("Daily briefing (chat)"):
            with st.spinner("Preparing briefing..."):
                result = run_chat("", st.session_state.session_id, None, briefing=True)
            st.session_state.session_id = result["session_id"]
            st.session_state.messages.append(
                {"role": "assistant", "content": sanitize_user_facing(result["reply"])}
            )
            st.rerun()
        if not USE_INPROCESS:
            st.info(f"API: {API_URL}")
    return fit_bands, days_ahead, top_n, active_profile


def tab_best_fits(fit_bands: list[str], days_ahead: int, top_n: int) -> None:
    st.subheader("Best fits")
    st.caption("Top opportunities for your active fit profile, ranked by fit band.")
    if not fit_bands:
        st.warning("Select at least one fit band in the sidebar.")
        return
    try:
        queue = fetch_queue(days_ahead, top_n, fit_bands)
    except Exception as exc:
        st.error(f"Could not load queue: {exc}")
        return

    if not queue:
        st.info(
            "No pending opportunities match your filters. "
            "Edit your fit profile or run `./run_daily.sh` after ingest."
        )
        return

    display = _rows_for_display(queue)
    st.dataframe(
        [{k: r.get(k) for k in QUEUE_COLUMNS if k in r} for r in display],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Export best fits CSV",
        _csv_bytes(queue),
        file_name="best_fits.csv",
        mime="text/csv",
    )

    st.divider()
    st.markdown("**Quick actions** — select a notice_id:")
    notice_ids = [r["notice_id"] for r in queue if r.get("notice_id")]
    selected = st.selectbox("Opportunity", notice_ids, key="queue_select_notice")
    if selected:
        row = next(r for r in queue if r.get("notice_id") == selected)
        band = row.get("fit_band") or "none"
        st.markdown(f"**{row.get('title', '')}** — _{FIT_BAND_LABELS.get(band, band)}_")
        link = row.get("ui_link") or ""
        if link:
            st.link_button("Open SAM.gov", link)
        notes = st.text_input("Notes (optional)", key="queue_action_notes")
        _review_buttons(selected, "queue", notes)


def tab_detail(days_ahead: int, active_profile: dict | None) -> None:
    st.subheader("Opportunity detail")
    agency_filter = st.text_input("Agency contains", key="browse_agency")
    naics_pick = _naics_selectbox(key="browse_naics")
    status_pick = st.selectbox(
        "Status",
        ["pending", "reviewing", "bid", "pass", "expired", ""],
        index=0,
        key="browse_status",
    )

    try:
        rows = _db().list_opportunities(
            status=status_pick or None,
            min_score=0,
            days_ahead=days_ahead if status_pick in ("", "pending") else None,
            agency_ilike=agency_filter or None,
            naics=naics_pick or None,
            limit=50,
        )
    except Exception as exc:
        st.error(f"Browse failed: {exc}")
        return

    if not rows:
        st.info("No rows match filters.")
        return

    notice_ids = [r["notice_id"] for r in rows if r.get("notice_id")]
    pick = st.selectbox("Select opportunity", notice_ids, key="detail_pick")
    row = next((r for r in rows if r.get("notice_id") == pick), None)
    if not row:
        return

    st.json({k: v for k, v in row.items() if k not in ("raw_data",)})
    link = row.get("ui_link") or ""
    if link:
        st.link_button("SAM.gov", link)
    notes = st.text_area("Notes", value=row.get("notes") or "", key="detail_notes")
    _review_buttons(pick, "detail", notes)


def tab_shortlist() -> None:
    st.subheader("Shortlist (reviewing + bid)")
    st.caption("Goal: keep 3–5 opportunities here for capture work.")
    try:
        rows = _db().get_shortlist() if USE_INPROCESS else []
    except Exception as exc:
        st.error(f"Could not load shortlist: {exc}")
        return

    if not rows:
        st.info("No shortlisted opportunities yet. Use Shortlist or Bid on the queue tab.")
        return

    st.metric("Shortlist size", len(rows))
    display = _rows_for_display(rows)
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button(
        "Export shortlist CSV",
        _csv_bytes(rows),
        file_name="shortlist.csv",
        mime="text/csv",
    )

    for row in rows:
        nid = row.get("notice_id")
        if not nid:
            continue
        with st.expander(f"[{row.get('review_status')}] {(row.get('title') or '')[:60]}"):
            if row.get("ui_link"):
                st.link_button("SAM.gov", row["ui_link"])
            notes = st.text_input("Notes", value=row.get("notes") or "", key=f"sl_notes_{nid}")
            _review_buttons(nid, f"sl_{nid}", notes)


def tab_chat() -> None:
    st.subheader("Chat with Counsel")
    if st.session_state.focus_notice_id:
        st.info(f"Focus: `{st.session_state.focus_notice_id}`")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            content = msg["content"]
            if msg["role"] == "assistant":
                content = sanitize_user_facing(content)
            st.markdown(content)

    prompt = st.chat_input("Ask about strategy, scores, or pass/bid...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("Thinking..."):
            result = run_chat(
                prompt,
                st.session_state.session_id,
                st.session_state.focus_notice_id,
            )
        st.session_state.session_id = result["session_id"]
        st.session_state.messages.append(
            {"role": "assistant", "content": sanitize_user_facing(result["reply"])}
        )
        if result.get("citations"):
            with st.expander("Sources"):
                for c in result["citations"]:
                    st.caption(sanitize_user_facing(c.get("source", "")))
                    st.text(sanitize_user_facing(c.get("snippet", "")))
        st.rerun()


def tab_fit_profile(active_profile: dict | None) -> None:
    st.subheader("My fit profile")
    st.caption(
        "Edit what your firm pursues. Saving updates Postgres; "
        "refresh scores to re-rank all opportunities."
    )

    try:
        profiles = list_fit_profiles()
    except Exception as exc:
        st.error(f"Could not load profiles: {exc}")
        return

    if not profiles:
        st.info("No profile in database. Run `./run_ingest.sh` to sync from match-profile.yaml.")
        return

    profile_id = active_profile["id"] if active_profile else profiles[0]["id"]
    profile = next((p for p in profiles if p["id"] == profile_id), profiles[0])

    if st.session_state.get("fit_profile_active_id") != profile_id:
        st.session_state.fit_profile_active_id = profile_id
        st.session_state.fit_profile_naics_draft = _list_to_lines(profile.get("naics_codes"))
    elif "fit_profile_naics_draft" not in st.session_state:
        st.session_state.fit_profile_naics_draft = _list_to_lines(profile.get("naics_codes"))

    with st.expander("Browse NAICS (2022 Census structure)", expanded=False):
        merged = _naics_profile_picker(
            key_prefix="profile_naics",
            selected_codes=_lines_to_list(st.session_state.fit_profile_naics_draft),
        )
        if merged != _lines_to_list(st.session_state.fit_profile_naics_draft):
            if st.button("Apply NAICS selection", key="profile_naics_apply"):
                st.session_state.fit_profile_naics_draft = _list_to_lines(merged)
                st.rerun()

    st.subheader("Geography")
    st.caption(
        "Show opportunities in your home state(s), plus remote work. "
        "On-site requirements in other states are hidden."
    )
    home_states_default = profile.get("home_states") or []
    include_remote_default = bool(profile.get("include_remote", True))
    include_unknown_default = bool(profile.get("include_unknown_location", False))

    with st.form("fit_profile_form"):
        name = st.text_input("Business name", value=profile.get("name") or "")
        slug = st.text_input("Slug", value=profile.get("slug") or "", disabled=True)
        capabilities = st.text_area(
            "Capability statement",
            value=profile.get("capabilities") or "",
            height=100,
        )
        home_states = st.multiselect(
            "Home state(s)",
            US_STATE_OPTIONS,
            default=[s for s in home_states_default if s in US_STATE_OPTIONS],
            help="Two-letter state codes where your firm can perform on-site work.",
        )
        g1, g2 = st.columns(2)
        with g1:
            include_remote = st.checkbox(
                "Include remote / nationwide opportunities",
                value=include_remote_default,
            )
        with g2:
            include_unknown = st.checkbox(
                "Include unknown location (no PopState in SAM)",
                value=include_unknown_default,
                help="Many notices omit place of performance; disable to cut more fat.",
            )
        c1, c2 = st.columns(2)
        with c1:
            naics_text = st.text_area(
                "NAICS codes you pursue (one per line)",
                value=st.session_state.fit_profile_naics_draft,
                height=140,
            )
            include_text = st.text_area(
                "Include keywords (one per line)",
                value=_list_to_lines(profile.get("include_keywords")),
                height=140,
            )
            exclude_sa_text = st.text_area(
                "Exclude set-asides (one per line)",
                value=_list_to_lines(profile.get("exclude_set_asides")),
                height=100,
            )
        with c2:
            psc_text = st.text_area(
                "PSC prefixes (one per line)",
                value=_list_to_lines(profile.get("psc_prefixes")),
                height=140,
            )
            exclude_text = st.text_area(
                "Exclude keywords (one per line)",
                value=_list_to_lines(profile.get("exclude_keywords")),
                height=140,
            )
            eligible_sa_text = st.text_area(
                "Eligible set-asides (optional, one per line)",
                value=_list_to_lines(profile.get("eligible_set_asides")),
                height=100,
            )

        save = st.form_submit_button("Save profile", type="primary")
        if save:
            payload = {
                "name": name.strip(),
                "capabilities": capabilities.strip() or None,
                "naics_codes": _lines_to_list(naics_text),
                "psc_prefixes": _lines_to_list(psc_text),
                "include_keywords": _lines_to_list(include_text),
                "exclude_keywords": _lines_to_list(exclude_text),
                "exclude_set_asides": _lines_to_list(exclude_sa_text),
                "eligible_set_asides": _lines_to_list(eligible_sa_text),
                "home_states": home_states,
                "include_remote": include_remote,
                "include_unknown_location": include_unknown,
            }
            try:
                save_fit_profile(profile_id, payload)
                st.session_state.fit_profile_naics_draft = _list_to_lines(payload["naics_codes"])
                st.success("Profile saved.")
            except Exception as exc:
                st.error(f"Save failed: {exc}")

    if st.button("Refresh scores from this profile", type="secondary"):
        with st.spinner("Recomputing match scores for all active opportunities…"):
            try:
                rows = refresh_profile_scores(profile_id)
                st.success(f"Updated scores for {rows:,} opportunities.")
            except Exception as exc:
                st.error(f"Refresh failed: {exc}")

    st.divider()
    st.caption(
        "CLI/cron still reads `config/match-profile.yaml` for ingest settings. "
        "Dashboard edits live in `fit_profiles`; run ingest to sync YAML → DB if you edit the file."
    )


def tab_fit_survey() -> None:
    st.subheader("Fit survey")
    st.caption("Was this opportunity a good project fit for you? This improves grading explanations.")

    try:
        shortlist = _db().get_shortlist(limit=50)
    except Exception:
        shortlist = []

    try:
        queue = _db().get_review_queue(top_n=25)
    except Exception:
        queue = []

    notice_ids = sorted(
        {r.get("notice_id") for r in shortlist + queue if r.get("notice_id")}
    )
    if not notice_ids:
        st.info("No opportunities available. Run ./run_daily.sh and ensure matches are in the queue.")
        return

    prefill_notice_id = st.session_state.get("fit_survey_notice_id")
    default_idx = 0
    if prefill_notice_id and prefill_notice_id in notice_ids:
        default_idx = notice_ids.index(prefill_notice_id)

    selected_notice_id = st.selectbox(
        "Opportunity (notice_id)",
        notice_ids,
        index=default_idx,
        key="fit_survey_notice_select",
    )

    opp = _db().get_opportunity(selected_notice_id)
    if not opp:
        st.error("Could not load opportunity details.")
        return

    st.divider()
    st.write(f"Title: {opp.get('title', '')}")
    st.write(f"Agency: {opp.get('agency', '')}")
    st.write(f"Fit band: {opp.get('fit_band', 'n/a')}")
    st.write(f"Current review_status: {opp.get('review_status', '')}")
    if opp.get("match_reasons"):
        st.caption(f"Match reasons: {opp.get('match_reasons')}")
    if opp.get("ui_link"):
        st.link_button("Open SAM.gov", opp["ui_link"], use_container_width=True)

    status_default = opp.get("review_status") or "pending"
    review_status = st.selectbox(
        "Survey status (tie it to what you decided)",
        ["pending", "reviewing", "bid", "pass", "expired"],
        index=["pending", "reviewing", "bid", "pass", "expired"].index(status_default)
        if status_default in {"pending", "reviewing", "bid", "pass", "expired"}
        else 0,
        key="fit_survey_review_status",
    )

    st.subheader("Rate fit")

    fit_rating = st.slider(
        "Overall fit for your firm (1–5)",
        1,
        5,
        3,
        key="fit_survey_fit_rating",
    )
    score_direction = st.selectbox(
        "Was the match score direction correct?",
        ["", "about_right", "too_high", "too_low"],
        index=0,
        key="fit_survey_score_direction",
    )
    score_accurate: bool | None = None
    if score_direction == "about_right":
        score_accurate = True
    elif score_direction in {"too_high", "too_low"}:
        score_accurate = False

    good_tags = st.multiselect(
        "Good tags",
        sorted(GOOD_TAGS),
        default=[],
        key="fit_survey_good_tags",
    )
    bad_tags = st.multiselect(
        "Bad tags",
        sorted(BAD_TAGS),
        default=[],
        key="fit_survey_bad_tags",
    )

    good_notes = st.text_area("Good notes (optional)")
    bad_notes = st.text_area("Bad notes (optional)")
    lessons_learned = st.text_area("Lessons learned (optional)")

    submitted = st.button("Submit fit survey", type="primary", key="fit_survey_submit")
    if submitted:
        ok = submit_fit_survey(
            selected_notice_id,
            review_status,
            fit_rating=fit_rating,
            score_accurate=score_accurate,
            score_direction=score_direction or None,
            good_tags=good_tags,
            bad_tags=bad_tags,
            good_notes=good_notes or None,
            bad_notes=bad_notes or None,
            lessons_learned=lessons_learned or None,
        )
        if ok:
            st.session_state.fit_survey_notice_id = None
            st.success("Fit survey saved (and indexed for RAG if embeddings are available).")
        else:
            st.error("Fit survey save failed.")


def main() -> None:
    st.set_page_config(page_title="Counsel", page_icon="📋", layout="wide")
    st.title("Counsel — Opportunity dashboard")
    st.caption("Review queue, shortlist picks, and capture copilot.")

    defaults = review_defaults()

    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "focus_notice_id" not in st.session_state:
        st.session_state.focus_notice_id = None
    if "fit_survey_notice_id" not in st.session_state:
        st.session_state.fit_survey_notice_id = None

    fit_bands, days_ahead, top_n, active_profile = render_sidebar(defaults)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Best fits", "My fit profile", "Browse / detail", "Shortlist", "Chat", "Fit survey"]
    )
    with tab1:
        tab_best_fits(fit_bands, days_ahead, top_n)
    with tab2:
        tab_fit_profile(active_profile)
    with tab3:
        tab_detail(days_ahead, active_profile)
    with tab4:
        tab_shortlist()
    with tab5:
        tab_chat()
    with tab6:
        tab_fit_survey()


if __name__ == "__main__":
    main()
