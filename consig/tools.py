"""OpenAI tool definitions and execution for Consig."""

from __future__ import annotations

import json
from typing import Any

from consig import db, rag

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
        return json.dumps({"error": f"unknown_tool:{name}"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})
