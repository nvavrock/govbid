"""FastAPI app for Consig."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from consig import chat, db, rag
from consig.config import load_env, review_defaults
from consig.survey_schema import (
    chunk_id_for_fit_survey,
    normalize_survey_payload,
    survey_row_to_rag_text,
)

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


class FitSurveyRequest(BaseModel):
    notice_id: str
    review_status: str
    fit_rating: int = Field(..., ge=1, le=5)
    score_accurate: bool | None = None
    score_direction: str | None = None
    good_tags: list[str] = Field(default_factory=list)
    bad_tags: list[str] = Field(default_factory=list)
    good_notes: str | None = None
    bad_notes: str | None = None
    lessons_learned: str | None = None


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


@app.get("/handoff/{notice_id}")
def handoff(notice_id: str) -> dict[str, Any]:
    """Phase 4 handoff payload stub for the (future) Research agent."""
    row = db.get_opportunity(notice_id)
    if not row:
        raise HTTPException(404, "Opportunity not found")
    if row.get("review_status") != "bid":
        raise HTTPException(400, "handoff is only available for opportunities with review_status='bid'")

    fit_surveys = []
    try:
        # Most recent survey first.
        fit_surveys = db.list_fit_surveys(notice_id=notice_id, limit=3)
    except Exception:
        pass

    return {
        "notice_id": notice_id,
        "review_status": row.get("review_status"),
        "opportunity": row,
        "latest_fit_survey": fit_surveys[0] if fit_surveys else None,
    }


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


@app.post("/fit-survey")
def fit_survey(req: FitSurveyRequest) -> dict[str, Any]:
    try:
        payload = normalize_survey_payload(
            fit_rating=req.fit_rating,
            score_accurate=req.score_accurate,
            score_direction=req.score_direction,
            good_tags=req.good_tags,
            bad_tags=req.bad_tags,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    saved = db.save_fit_survey(
        req.notice_id,
        req.review_status,
        fit_rating=payload["fit_rating"],
        score_accurate=payload["score_accurate"],
        score_direction=payload["score_direction"],
        good_tags=payload["good_tags"],
        bad_tags=payload["bad_tags"],
        good_notes=req.good_notes,
        bad_notes=req.bad_notes,
        lessons_learned=req.lessons_learned,
    )

    survey_id = saved.get("id")
    if not survey_id:
        return saved

    # Index into Chroma immediately so future chat explanations can retrieve it.
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

    return saved
