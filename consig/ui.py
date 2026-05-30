"""Streamlit UI for Consig capture copilot and Phase 2 opportunity dashboard."""

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

from consig.config import load_env, review_defaults  # noqa: E402
from consig.survey_schema import (
    BAD_TAGS,
    GOOD_TAGS,
    chunk_id_for_fit_survey,
    normalize_survey_payload,
    survey_row_to_rag_text,
)

load_env()

API_URL = os.environ.get("CONSIG_API_URL", "http://127.0.0.1:8000").rstrip("/")
USE_INPROCESS = os.environ.get("CONSIG_INPROCESS", "1") == "1"

QUEUE_COLUMNS = [
    "rule_score",
    "title",
    "agency",
    "posted_date",
    "response_deadline",
    "naics",
    "psc",
    "set_aside",
    "procurement_type",
    "match_reasons",
    "notice_id",
    "ui_link",
]


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
    from consig import chat

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
    from consig import db

    return db


def fetch_queue(min_score: int | None, days_ahead: int | None, top_n: int | None) -> list:
    if USE_INPROCESS:
        return _db().get_review_queue(
            min_score=min_score, days_ahead=days_ahead, top_n=top_n
        )
    return _api_get(
        "/queue",
        min_score=min_score,
        days_ahead=days_ahead,
        top_n=top_n,
    )


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
        from consig import rag

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


def render_sidebar(defaults: dict) -> tuple[int, int, int]:
    with st.sidebar:
        st.subheader("Queue filters")
        min_score = st.slider(
            "Min score",
            0,
            100,
            int(defaults["min_score"]),
            key="filter_min_score",
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
        st.caption("Edit defaults in `config/match-profile.yaml`")

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
                {"role": "assistant", "content": result["reply"]}
            )
            st.rerun()
        if not USE_INPROCESS:
            st.info(f"API: {API_URL}")
    return min_score, days_ahead, top_n


def tab_queue(min_score: int, days_ahead: int, top_n: int) -> None:
    st.subheader("Today's queue")
    try:
        queue = fetch_queue(min_score, days_ahead, top_n)
    except Exception as exc:
        st.error(f"Could not load queue: {exc}")
        return

    if not queue:
        st.info("No pending opportunities. Run `./run_daily.sh` or tune match-profile.yaml.")
        return

    display = _rows_for_display(queue)
    st.dataframe(
        [{k: r.get(k) for k in QUEUE_COLUMNS if k in r} for r in display],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Export queue CSV",
        _csv_bytes(queue),
        file_name="review_queue.csv",
        mime="text/csv",
    )

    st.divider()
    st.markdown("**Quick actions** — select a notice_id:")
    notice_ids = [r["notice_id"] for r in queue if r.get("notice_id")]
    selected = st.selectbox("Opportunity", notice_ids, key="queue_select_notice")
    if selected:
        row = next(r for r in queue if r.get("notice_id") == selected)
        st.markdown(f"**{row.get('title', '')}**")
        link = row.get("ui_link") or ""
        if link:
            st.link_button("Open SAM.gov", link)
        notes = st.text_input("Notes (optional)", key="queue_action_notes")
        _review_buttons(selected, "queue", notes)


def tab_detail(min_score: int, days_ahead: int) -> None:
    st.subheader("Opportunity detail")
    from lib.match_profile import load_profile

    profile = load_profile()
    agency_filter = st.text_input("Agency contains", key="browse_agency")
    naics_opts = [""] + profile.get("naics_codes", [])
    naics_pick = st.selectbox("NAICS", naics_opts, key="browse_naics")
    status_pick = st.selectbox(
        "Status",
        ["pending", "reviewing", "bid", "pass", "expired", ""],
        index=0,
        key="browse_status",
    )

    try:
        rows = _db().list_opportunities(
            status=status_pick or None,
            min_score=min_score,
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
    st.subheader("Chat with Consig")
    if st.session_state.focus_notice_id:
        st.info(f"Focus: `{st.session_state.focus_notice_id}`")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

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
            {"role": "assistant", "content": result["reply"]}
        )
        if result.get("citations"):
            with st.expander("Sources"):
                for c in result["citations"]:
                    st.caption(c.get("source", ""))
                    st.text(c.get("snippet", ""))
        st.rerun()


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
    st.write(f"Score: {opp.get('rule_score', '')}")
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
    st.set_page_config(page_title="Consig", page_icon="📋", layout="wide")
    st.title("Consig — Opportunity dashboard")
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

    min_score, days_ahead, top_n = render_sidebar(defaults)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Today's queue", "Browse / detail", "Shortlist", "Chat", "Fit survey"]
    )
    with tab1:
        tab_queue(min_score, days_ahead, top_n)
    with tab2:
        tab_detail(min_score, days_ahead)
    with tab3:
        tab_shortlist()
    with tab4:
        tab_chat()
    with tab5:
        tab_fit_survey()


if __name__ == "__main__":
    main()
