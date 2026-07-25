"""The signed-in listener's own view: their profile, history and recommendations."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount, StorageDep
from app.domain.models import UserProfile
from app.domain.schemas import MyRecommendationRequest

router = APIRouter(prefix="/me", tags=["me"])


@router.post("/recommendations", summary="Recommendations for the signed-in listener")
async def my_recommendations(
    payload: MyRecommendationRequest, container: StorageDep, account: CurrentAccount
) -> dict:
    """Same ranker as POST /recommendations, with the listener taken from the token."""
    user = await container.users_repo.get(account.user_id) or UserProfile(
        user_id=account.user_id, is_cold_start=True
    )
    context = await container.cache.get()
    result = container.ranking.recommend(
        user,
        context,
        limit=payload.limit,
        language=payload.language,
        exclude=set(payload.exclude_content_ids),
        include_seen=payload.include_seen,
        diversity=payload.diversity,
        include_duplicates=payload.include_duplicates,
    )

    explanation, source = (result.explanation, "deterministic")
    if payload.explain:
        explanation, source = await container.explanation.explain_recommendations(result, user)

    return result.model_dump(mode="json") | {
        "explanation": explanation,
        "explanation_source": source,
        "account": {"user_id": account.user_id, "display_name": account.display_name},
        "profile_built": user.events_observed > 0,
        "note": (
            "A newly registered listener is a cold start until they log activity and the "
            "pipeline runs. POST /pipeline/run rebuilds profiles from the current log."
        ),
    }


@router.get("/profile", summary="The signed-in listener's derived taste profile")
async def my_profile(container: StorageDep, account: CurrentAccount) -> dict:
    profile = await container.users_repo.get(account.user_id)
    if profile is None:
        return {
            "account": account.public(),
            "profile_built": False,
            "note": (
                "No taste profile yet. Log listening events via POST /activity, then run "
                "POST /pipeline/run to build one."
            ),
        }
    payload = profile.model_dump(mode="json")
    payload["taste_vector"] = {
        "dimensions": len(profile.taste_vector),
        "available": bool(profile.taste_vector),
    }
    return {"account": account.public(), "profile_built": True, "profile": payload}


@router.get("/history", summary="The signed-in listener's own event log")
async def my_history(
    container: StorageDep,
    account: CurrentAccount,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    events = await container.activity_repo.for_user(account.user_id, limit=limit)
    titles = {
        item.content_id: item.title
        for item in await container.content_repo.get_many(
            sorted({event.content_id for event in events if event.content_id})
        )
    }
    return {
        "user_id": account.user_id,
        "events": len(events),
        "history": [
            {
                "occurred_at": event.occurred_at,
                "event_type": event.event_type.value,
                "content_id": event.content_id,
                "title": titles.get(event.content_id or ""),
                "position_seconds": event.position_seconds,
                "chapter_index": event.chapter_index,
                "query": event.query,
                "is_synthetic": event.is_synthetic,
            }
            for event in events
        ],
    }
