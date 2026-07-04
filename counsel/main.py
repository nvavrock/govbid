"""FastAPI app for Counsel."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from counsel import chat, db, rag
from counsel.config import load_env, review_defaults
from counsel.survey_schema import (
    chunk_id_for_fit_survey,
    normalize_survey_payload,
    survey_row_to_rag_text,
)

load_env()

app = FastAPI(title="Counsel", version="0.1.0")


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


class FitProfileCreate(BaseModel):
    slug: str
    name: str
    capabilities: str | None = None
    naics_codes: list[str] = Field(default_factory=list)
    psc_prefixes: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    exclude_set_asides: list[str] = Field(default_factory=list)
    eligible_set_asides: list[str] = Field(default_factory=list)
    home_states: list[str] = Field(default_factory=list)
    include_remote: bool = True
    include_unknown_location: bool = False
    is_default: bool = False


class FitProfileUpdate(BaseModel):
    slug: str | None = None
    name: str | None = None
    capabilities: str | None = None
    naics_codes: list[str] | None = None
    psc_prefixes: list[str] | None = None
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    exclude_set_asides: list[str] | None = None
    eligible_set_asides: list[str] | None = None
    home_states: list[str] | None = None
    include_remote: bool | None = None
    include_unknown_location: bool | None = None
    is_default: bool | None = None


class RefreshScoresResponse(BaseModel):
    profile_id: int
    rows_updated: int


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "chroma_chunks": rag.collection_count(),
    }


@app.get("/naics")
def distinct_naics(limit: int = Query(5000, ge=1, le=10000)) -> list[str]:
    return db.list_distinct_naics(limit=limit)


@app.get("/queue")
def queue(
    days_ahead: int | None = None,
    min_score: int | None = None,
    top_n: int | None = None,
    fit_bands: str | None = Query(None, description="Comma-separated: strong,good,stretch"),
) -> list[dict[str, Any]]:
    bands = [b.strip() for b in fit_bands.split(",") if b.strip()] if fit_bands else None
    return db.get_review_queue(
        days_ahead=days_ahead,
        min_score=min_score,
        top_n=top_n,
        fit_bands=bands,
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


@app.get("/fit-profiles")
def list_fit_profiles() -> list[dict[str, Any]]:
    return db.list_fit_profiles()


@app.get("/fit-profiles/{profile_id}")
def get_fit_profile(profile_id: int) -> dict[str, Any]:
    row = db.get_fit_profile(profile_id)
    if not row:
        raise HTTPException(404, "Fit profile not found")
    return row


@app.post("/fit-profiles")
def create_fit_profile(req: FitProfileCreate) -> dict[str, Any]:
    try:
        return db.create_fit_profile(
            slug=req.slug,
            name=req.name,
            capabilities=req.capabilities,
            naics_codes=req.naics_codes,
            psc_prefixes=req.psc_prefixes,
            include_keywords=req.include_keywords,
            exclude_keywords=req.exclude_keywords,
            exclude_set_asides=req.exclude_set_asides,
            eligible_set_asides=req.eligible_set_asides,
            home_states=req.home_states,
            include_remote=req.include_remote,
            include_unknown_location=req.include_unknown_location,
            is_default=req.is_default,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/fit-profiles/{profile_id}")
def update_fit_profile(profile_id: int, req: FitProfileUpdate) -> dict[str, Any]:
    try:
        return db.update_fit_profile(
            profile_id,
            slug=req.slug,
            name=req.name,
            capabilities=req.capabilities,
            naics_codes=req.naics_codes,
            psc_prefixes=req.psc_prefixes,
            include_keywords=req.include_keywords,
            exclude_keywords=req.exclude_keywords,
            exclude_set_asides=req.exclude_set_asides,
            eligible_set_asides=req.eligible_set_asides,
            home_states=req.home_states,
            include_remote=req.include_remote,
            include_unknown_location=req.include_unknown_location,
            is_default=req.is_default,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/fit-profiles/{profile_id}")
def delete_fit_profile(profile_id: int) -> dict[str, str]:
    try:
        db.delete_fit_profile(profile_id)
        return {"ok": "true"}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/fit-profiles/{profile_id}/refresh-scores")
def refresh_fit_profile_scores(profile_id: int) -> RefreshScoresResponse:
    try:
        rows = db.refresh_scores_for_profile(profile_id)
        return RefreshScoresResponse(profile_id=profile_id, rows_updated=rows)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


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
