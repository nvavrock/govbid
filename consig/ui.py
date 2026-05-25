"""Streamlit UI for Consig capture copilot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from consig.config import load_env, review_defaults  # noqa: E402

load_env()

API_URL = os.environ.get("CONSIG_API_URL", "http://127.0.0.1:8000").rstrip("/")
USE_INPROCESS = os.environ.get("CONSIG_INPROCESS", "1") == "1"


def _api_get(path: str, **params) -> object:
    with httpx.Client(timeout=120.0) as client:
        r = client.get(f"{API_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


def _api_post(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=180.0) as client:
        r = client.post(f"{API_URL}{path}", json=payload)
        r.raise_for_status()
        return r.json()


def _chat_inprocess(message: str, session_id: str | None, notice_id: str | None, briefing: bool) -> dict:
    from consig import chat

    if briefing:
        return chat.daily_briefing(session_id=session_id)
    return chat.handle_chat(message, session_id=session_id, notice_id=notice_id)


def _queue_inprocess() -> list:
    from consig import db

    return db.get_review_queue()


def run_chat(message: str, session_id: str | None, notice_id: str | None, briefing: bool = False) -> dict:
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


def fetch_queue() -> list:
    if USE_INPROCESS:
        return _queue_inprocess()
    return _api_get("/queue")


def main() -> None:
    st.set_page_config(page_title="Consig", page_icon="📋", layout="wide")
    st.title("Consig — Capture copilot")
    st.caption("Review scored SAM opportunities with guidance.")

    defaults = review_defaults()

    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "focus_notice_id" not in st.session_state:
        st.session_state.focus_notice_id = None

    with st.sidebar:
        st.subheader("Session")
        if st.button("New session"):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()

        if st.button("Daily briefing"):
            with st.spinner("Consig is preparing your briefing..."):
                result = run_chat("", st.session_state.session_id, None, briefing=True)
            st.session_state.session_id = result["session_id"]
            st.session_state.messages.append(
                {"role": "assistant", "content": result["reply"]}
            )
            st.rerun()

        st.divider()
        st.subheader("Review queue params")
        st.text(f"min_score: {defaults['min_score']}")
        st.text(f"days_ahead: {defaults['days_ahead']}")
        st.text(f"top_n: {defaults['top_n']}")
        if not USE_INPROCESS:
            st.info(f"API: {API_URL}")

    col_chat, col_queue = st.columns([1.2, 1])

    with col_queue:
        st.subheader("Pending opportunities")
        try:
            queue = fetch_queue()
        except Exception as exc:
            st.error(f"Could not load queue: {exc}")
            queue = []

        if queue:
            for row in queue:
                label = f"[{row.get('rule_score')}] {(row.get('title') or '')[:50]}"
                if st.button(label, key=f"pick_{row.get('notice_id')}"):
                    st.session_state.focus_notice_id = row.get("notice_id")
                    st.session_state.messages.append(
                        {
                            "role": "user",
                            "content": f"I want to focus on notice_id {row.get('notice_id')}. "
                            f"Explain the score and whether I should pursue capture.",
                        }
                    )
                    result = run_chat(
                        st.session_state.messages[-1]["content"],
                        st.session_state.session_id,
                        st.session_state.focus_notice_id,
                    )
                    st.session_state.session_id = result["session_id"]
                    st.session_state.messages.append(
                        {"role": "assistant", "content": result["reply"]}
                    )
                    st.rerun()

                link = row.get("ui_link") or ""
                if link:
                    st.link_button("SAM.gov", link, use_container_width=True)
                st.caption(
                    f"{row.get('agency', '')} | deadline {row.get('response_deadline', 'n/a')}"
                )
                st.divider()
        else:
            st.info("No pending opportunities in queue.")

    with col_chat:
        st.subheader("Chat")
        if st.session_state.focus_notice_id:
            st.info(f"Focus: `{st.session_state.focus_notice_id}`")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ask Consig about strategy, scores, or pass/bid...")
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


if __name__ == "__main__":
    main()
