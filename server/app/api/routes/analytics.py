"""Per-item and per-listener behavioural analytics."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import StorageDep
from app.core.errors import NotFoundError

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/content/{content_id}", summary="Retention curve, chapter interest and abandon point")
async def content_analytics(content_id: str, container: StorageDep) -> dict:
    item = await container.content_repo.get(content_id)
    if item is None:
        raise NotFoundError(f"No catalog item with id '{content_id}'.")
    features = await container.features_repo.get(content_id)
    if features is None:
        raise NotFoundError(
            f"No features computed for '{content_id}' yet.",
            details={"hint": "POST /pipeline/run to build features from the current event log."},
        )
    return {
        "content_id": content_id,
        "title": item.title,
        "duration_seconds": item.duration_seconds,
        "features": features.model_dump(mode="json"),
    }


@router.get("/content/{content_id}/drop-off", summary="Plain-English drop-off diagnosis")
async def drop_off(content_id: str, container: StorageDep) -> dict:
    item = await container.content_repo.get(content_id)
    if item is None:
        raise NotFoundError(f"No catalog item with id '{content_id}'.")
    features = await container.features_repo.get(content_id)
    if features is None:
        raise NotFoundError(
            f"No features computed for '{content_id}' yet.",
            details={"hint": "POST /pipeline/run first."},
        )
    explanation, source = await container.explanation.explain_drop_off(item, features)
    weakest = min(features.chapter_interest, key=lambda row: row.interest_score, default=None)
    return {
        "content_id": content_id,
        "title": item.title,
        "explanation": explanation,
        "explanation_source": source,
        "completion_rate": features.completion_rate,
        "drop_off_rate": features.drop_off_rate,
        "median_abandon_seconds": features.median_abandon_seconds,
        "abandon_point_ratio": features.abandon_point_ratio,
        "weakest_chapter": weakest.model_dump(mode="json") if weakest else None,
        "retention_curve": [point.model_dump(mode="json") for point in features.retention_curve],
        "sample_size": features.sample_size,
        "confidence": features.confidence.value,
        "provenance": features.provenance.value,
    }


@router.get("/user/{user_id}", summary="Derived listener taste profile")
async def user_analytics(user_id: str, container: StorageDep) -> dict:
    profile = await container.users_repo.get(user_id)
    if profile is None:
        raise NotFoundError(
            f"No profile for user '{user_id}'.",
            details={"hint": "Log activity for this user, then POST /pipeline/run."},
        )
    payload = profile.model_dump(mode="json")
    # The raw vector is large and meaningless to a human; report its shape instead.
    payload["taste_vector"] = {
        "dimensions": len(profile.taste_vector),
        "available": bool(profile.taste_vector),
    }
    return payload


@router.get("/creators/{creator_id}", summary="Portfolio view for one creator")
async def creator_analytics(creator_id: str, container: StorageDep) -> dict:
    items = await container.content_repo.list_catalog(creator_id=creator_id, limit=500)
    if not items:
        raise NotFoundError(f"No catalog items for creator '{creator_id}'.")
    features = await container.features_repo.get_many([item.content_id for item in items])
    profiles = await container.profile_repo.get_many([item.content_id for item in items])

    measured = [features[item.content_id] for item in items if item.content_id in features]
    return {
        "creator_id": creator_id,
        "catalog_items": len(items),
        "items_with_measurements": len(measured),
        "avg_completion_rate": (
            round(sum(row.completion_rate for row in measured) / len(measured), 4) if measured else None
        ),
        "avg_drop_off_rate": (
            round(sum(row.drop_off_rate for row in measured) / len(measured), 4) if measured else None
        ),
        "total_unique_listeners": sum(row.unique_listeners for row in measured),
        "items": [
            {
                "content_id": item.content_id,
                "title": item.title,
                "language": item.language,
                "genres": item.genres,
                "completion_rate": features[item.content_id].completion_rate
                if item.content_id in features
                else None,
                "drop_off_rate": features[item.content_id].drop_off_rate
                if item.content_id in features
                else None,
                "unique_listeners": features[item.content_id].unique_listeners
                if item.content_id in features
                else 0,
                "originality_score": profiles[item.content_id].originality_score
                if item.content_id in profiles
                else None,
                "duplicate_kind": profiles[item.content_id].duplicate_kind.value
                if item.content_id in profiles
                else None,
            }
            for item in items
        ],
    }
