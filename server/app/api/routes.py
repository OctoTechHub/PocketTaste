"""HTTP layer — thin controllers that validate input and delegate to services.

Handlers are declared ``def`` (not ``async def``) so FastAPI runs them in a
threadpool; the underlying pymongo + OpenAI clients are synchronous.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.data.repositories import event_repository, series_repository, user_repository
from app.domain.models import BehaviorEvent
from app.domain.scoring import cosine, score_series
from app.services.candidate_service import Candidate
from app.services.context_service import get_catalog, invalidate_context
from app.services.discovery_service import discover
from app.services.explain_service import attach_explanations
from app.services.recommendation_service import build_feed, build_profile, similar_series
from app.api.schemas import DiscoverRequest, EventRequest
from app.api.serializers import public_profile, public_ranked, public_rail, public_series

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": "openai" if settings.has_openai else "local-fallback",
        "catalogSize": series_repository.count(),
    }


@router.get("/users")
def list_users() -> dict:
    users = user_repository.find_all()
    return {
        "users": [
            {"id": u.id, "displayName": u.display_name, "languages": u.languages}
            for u in users
        ]
    }


@router.get("/series")
def list_series() -> dict:
    return {"series": [public_series(s) for s in get_catalog()]}


@router.get("/series/{series_id}")
def get_series(series_id: str) -> dict:
    s = series_repository.find_by_id(series_id)
    if s is None:
        raise HTTPException(status_code=404, detail="series not found")
    return {
        "series": public_series(s),
        "similar": [public_ranked(r) for r in similar_series(series_id)],
    }


@router.get("/feed")
def feed(user_id: str) -> dict:
    rails = build_feed(user_id)
    return {"rails": [public_rail(r) for r in rails]}


@router.get("/profile")
def profile(user_id: str) -> dict:
    prof, _ = build_profile(user_id)
    return {"profile": public_profile(prof)}


@router.post("/discover")
def discover_route(body: DiscoverRequest) -> dict:
    prof, catalog = build_profile(body.user_id or "_anon")
    results, intent = discover(body.user_id, body.query, prof, catalog)
    return {
        "intent": {
            "genres": intent.genres,
            "excludeGenres": intent.exclude_genres,
            "language": intent.language,
            "tones": intent.tones,
            "pacing": intent.pacing,
            "maxEpisodeMinutes": intent.max_episode_minutes,
            "keywords": intent.keywords,
            "moodText": intent.mood_text,
        },
        "results": [public_ranked(r) for r in results],
    }


@router.post("/events")
def log_event(body: EventRequest) -> dict:
    event = BehaviorEvent(
        user_id=body.user_id,
        series_id=body.series_id,
        type=body.type,
        episode_index=body.episode_index,
        completion_pct=body.completion_pct,
        coins=body.coins,
        value=body.value,
        session_id=body.session_id,
        ts=int(time.time() * 1000),
    )
    event_repository.append(event)
    invalidate_context()  # co-occurrence index may have changed
    return {"ok": True}


@router.get("/explain")
def explain(user_id: str, series_id: str) -> dict:
    prof, catalog = build_profile(user_id)
    s = series_repository.find_by_id(series_id)
    if s is None:
        raise HTTPException(status_code=404, detail="series not found")
    sim = max(0.0, cosine(prof.taste_vector, s.embedding))
    bd = score_series(prof, s, sim)
    from app.domain.models import RankedSeries

    ranked = RankedSeries(series=s, score=bd.total, breakdown=bd, sources=["content"])
    attach_explanations(prof, [ranked], catalog, use_llm=settings.has_openai)
    return {"explanation": ranked.reason, "breakdown": public_ranked(ranked)["breakdown"]}
