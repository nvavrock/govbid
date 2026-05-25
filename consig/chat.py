"""Chat orchestration with OpenAI tools and session persistence."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from consig.config import llm_model, openai_api_key
from consig import db, rag
from consig.prompts import SYSTEM_PROMPT, build_context_block, profile_summary
from consig.tools import TOOL_SCHEMAS, run_tool

MAX_TOOL_ROUNDS = 6


def _client() -> OpenAI:
    return OpenAI(api_key=openai_api_key())


def _messages_for_api(
    session_id: str | None,
    user_message: str,
    notice_id: str | None,
    *,
    briefing: bool = False,
) -> list[dict[str, Any]]:
    queue = db.get_review_queue()
    opportunity = db.get_opportunity(notice_id) if notice_id else None
    preferences = db.get_preferences()
    query = user_message if not briefing else "daily capture briefing top opportunities"
    rag_chunks = rag.search(query)

    context = build_context_block(
        queue=queue,
        opportunity=opportunity,
        preferences=preferences,
        rag_chunks=rag_chunks,
    )
    profile = profile_summary()

    system = SYSTEM_PROMPT
    if profile:
        system += f"\n\n## Match profile (reference)\n{profile[:3000]}"
    if context:
        system += f"\n\n{context}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

    if session_id:
        history = db.get_session_messages(session_id)
        for msg in history[-30:]:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

    if briefing:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Give me today's capture briefing: top pending opportunities from the queue, "
                    "why each scored well, urgency by deadline, and recommended next step for the top 5."
                ),
            }
        )
    else:
        messages.append({"role": "user", "content": user_message})

    return messages


def handle_chat(
    message: str,
    *,
    session_id: str | None = None,
    notice_id: str | None = None,
    briefing: bool = False,
) -> dict[str, Any]:
    if not session_id:
        session_id = db.create_session()

    if not briefing:
        db.append_message(session_id, "user", message, notice_id)

    messages = _messages_for_api(session_id, message, notice_id, briefing=briefing)
    client = _client()
    actions_taken: list[str] = []
    citations: list[dict[str, str]] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=llm_model(),
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = run_tool(tc.function.name, args)
                actions_taken.append(f"{tc.function.name}({args})")
                if tc.function.name == "search_corpus":
                    try:
                        hits = json.loads(result)
                        for h in hits[:3]:
                            citations.append(
                                {
                                    "source": h.get("source", ""),
                                    "snippet": (h.get("text") or "")[:200],
                                }
                            )
                    except json.JSONDecodeError:
                        pass
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        reply = (msg.content or "").strip()
        db.append_message(session_id, "assistant", reply, notice_id)
        return {
            "session_id": session_id,
            "reply": reply,
            "citations": citations,
            "actions_taken": actions_taken,
        }

    reply = "I hit the tool call limit. Please try a simpler question."
    db.append_message(session_id, "assistant", reply, notice_id)
    return {
        "session_id": session_id,
        "reply": reply,
        "citations": citations,
        "actions_taken": actions_taken,
    }


def daily_briefing(session_id: str | None = None) -> dict[str, Any]:
    return handle_chat("", session_id=session_id, briefing=True)
