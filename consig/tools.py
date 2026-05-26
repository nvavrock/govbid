"""OpenAI tool definitions and execution for Consig."""

from __future__ import annotations

import json
from typing import Any

from consig import db, rag
from consig.survey_schema import (
    chunk_id_for_fit_survey,
    normalize_survey_payload,
    survey_row_to_rag_text,
)

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_review_queue",
            "description": "Get top pending opportunities scored for IT/software fit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Deadline window in days"},
                    "min_score": {"type": "integer", "description": "Minimum rule_score"},
                    "top_n": {"type": "integer", "description": "Max rows to return"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_opportunity",
            "description": "Get full details and match score for one SAM notice_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notice_id": {"type": "string", "description": "SAM NoticeId UUID"},
                },
                "required": ["notice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_review_status",
            "description": "Update human review status for an opportunity (pass, bid, reviewing, pending, expired).",
            "parameters": {
                "type": "object",
                "properties": {
                    "notice_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "reviewing", "bid", "pass", "expired"],
                    },
                    "notes": {"type": "string", "description": "Optional reviewer notes"},
                },
                "required": ["notice_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_corpus",
            "description": "Search GovClose transcripts and playbooks for federal contracting guidance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_preferences",
            "description": "Get saved org capture preferences.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_preference",
            "description": "Save an org capture preference (e.g. avoid certain set-asides).",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string", "description": "Preference value as text"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_fit_survey",
            "description": "Record structured feedback on whether this project/opportunity was a good fit for the firm; indexes for RAG explanations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notice_id": {"type": "string"},
                    "review_status": {
                        "type": "string",
                        "enum": ["pending", "reviewing", "bid", "pass", "expired"],
                    },
                    "fit_rating": {"type": "integer", "description": "1-5 overall fit rating"},
                    "score_accurate": {"type": "boolean", "description": "Was the match score accurate?"},
                    "score_direction": {
                        "type": "string",
                        "enum": ["too_high", "too_low", "about_right"],
                    },
                    "good_tags": {"type": "array", "items": {"type": "string"}},
                    "bad_tags": {"type": "array", "items": {"type": "string"}},
                    "good_notes": {"type": "string"},
                    "bad_notes": {"type": "string"},
                    "lessons_learned": {"type": "string"},
                },
                "required": ["notice_id", "review_status", "fit_rating"],
            },
        },
    },
]


def run_tool(name: str, arguments: dict[str, Any]) -> str:
    try:
        if name == "get_review_queue":
            rows = db.get_review_queue(
                days_ahead=arguments.get("days_ahead"),
                min_score=arguments.get("min_score"),
                top_n=arguments.get("top_n"),
            )
            return json.dumps(rows, default=str)
        if name == "get_opportunity":
            row = db.get_opportunity(arguments["notice_id"])
            if not row:
                return json.dumps({"error": "not_found"})
            return json.dumps(row, default=str)
        if name == "set_review_status":
            row = db.set_review_status(
                arguments["notice_id"],
                arguments["status"],
                arguments.get("notes"),
            )
            db.record_feedback(
                arguments["notice_id"],
                arguments["status"],
                arguments.get("notes"),
            )
            return json.dumps(row, default=str)
        if name == "search_corpus":
            hits = rag.search(arguments["query"])
            return json.dumps(hits, default=str)
        if name == "get_preferences":
            return json.dumps(db.get_preferences(), default=str)
        if name == "set_preference":
            db.set_preference(arguments["key"], arguments["value"])
            return json.dumps({"ok": True, "key": arguments["key"]})
        if name == "record_fit_survey":
            payload = normalize_survey_payload(
                fit_rating=int(arguments["fit_rating"]),
                score_accurate=arguments.get("score_accurate"),
                score_direction=arguments.get("score_direction"),
                good_tags=arguments.get("good_tags"),
                bad_tags=arguments.get("bad_tags"),
            )
            saved = db.save_fit_survey(
                arguments["notice_id"],
                arguments["review_status"],
                fit_rating=payload["fit_rating"],
                score_accurate=payload["score_accurate"],
                score_direction=payload["score_direction"],
                good_tags=payload["good_tags"],
                bad_tags=payload["bad_tags"],
                good_notes=arguments.get("good_notes"),
                bad_notes=arguments.get("bad_notes"),
                lessons_learned=arguments.get("lessons_learned"),
            )

            survey_id = saved.get("id")
            if survey_id:
                try:
                    row = db.get_fit_survey_by_id(int(survey_id))
                    if row:
                        rag.index_chunks(
                            [
                                {
                                    "id": chunk_id_for_fit_survey(int(survey_id)),
                                    "text": survey_row_to_rag_text(row),
                                    "source": f"fit_feedback/survey_{survey_id}",
                                    "title": "fit_feedback",
                                }
                            ],
                            reset=False,
                        )
                        db.mark_fit_survey_indexed(int(survey_id))
                        saved["indexed_at"] = True
                except Exception:
                    saved["indexed_at"] = False
            return json.dumps(saved, default=str)
        return json.dumps({"error": f"unknown_tool:{name}"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})
