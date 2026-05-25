"""FastAPI app for Consig."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from consig import chat, db, rag
from consig.config import load_env, review_defaults

load_env()

app = FastAPI(title="Consig", version="0.1.0")


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = ""
    notice_id: str | None = None
    briefing: bool = False


class ReviewRequest(BaseModel):
    notice_id: str
    status: str
    notes: str | None = None


class PreferenceRequest(BaseModel):
    key: str
    value: str


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "chroma_chunks": rag.collection_count(),
    }


@app.get("/queue")
def queue(
    days_ahead: int | None = None,
    min_score: int | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    return db.get_review_queue(
        days_ahead=days_ahead,
        min_score=min_score,
        top_n=top_n,
    )


@app.get("/opportunity/{notice_id}")
def opportunity(notice_id: str) -> dict[str, Any]:
    row = db.get_opportunity(notice_id)
    if not row:
        raise HTTPException(404, "Opportunity not found")
    return row


@app.post("/chat")
def post_chat(req: ChatRequest) -> dict[str, Any]:
    if req.briefing:
        return chat.daily_briefing(session_id=req.session_id)
    if not req.message.strip():
        raise HTTPException(400, "message is required unless briefing=true")
    return chat.handle_chat(
        req.message,
        session_id=req.session_id,
        notice_id=req.notice_id,
    )


@app.post("/review")
def post_review(req: ReviewRequest) -> dict[str, Any]:
    try:
        row = db.set_review_status(req.notice_id, req.status, req.notes)
        db.record_feedback(req.notice_id, req.status, req.notes)
        return row
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/sessions")
def sessions(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    return db.list_sessions(limit=limit)


@app.get("/preferences")
def get_preferences() -> dict[str, Any]:
    return db.get_preferences()


@app.post("/preferences")
def post_preference(req: PreferenceRequest) -> dict[str, str]:
    db.set_preference(req.key, req.value)
    return {"ok": "true", "key": req.key}


@app.get("/review-defaults")
def review_params() -> dict[str, int]:
    return review_defaults()
