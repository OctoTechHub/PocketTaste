"""The recommendation endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep, StorageDep
from app.core.errors import NotFoundError
from app.domain.models import UserProfile
from app.domain.schemas import RecommendationRequest

router = APIRouter(tags=["recommendations"])


@router.post("/recommendations", summary="Personalised hybrid recommendations")
async def recommend(payload: RecommendationRequest, container: StorageDep) -> dict:
    """Every returned item carries its full signal breakdown and the weight applied
    to each signal, so the score can be recomputed by hand."""
    user = await container.users_repo.get(payload.user_id)
    if user is None:
        # Unknown user is a legitimate cold-start case, not an error.
        user = UserProfile(user_id=payload.user_id, is_cold_start=True)

    context = await container.cache.get()
    if not context.catalog:
        raise NotFoundError(
            "Catalog is empty.", details={"hint": "Load content via POST /catalog or scripts/seed.py."}
        )

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
        "listener_state": {
            "known_user": user.events_observed > 0,
            "positive_interactions": len(user.positive_content_ids),
            "top_genres": sorted(user.genre_affinity, key=user.genre_affinity.get, reverse=True)[:4],
            "languages": sorted(user.language_affinity, key=user.language_affinity.get, reverse=True),
            "pacing_preference": user.pacing_preference.value,
            "completion_propensity": user.completion_propensity,
        },
        "scoring_note": (
            "final_score is the MMR value used for ordering; relevance_score is the raw linear "
            "blend. contributions sum to relevance_score."
        ),
        "duplicate_policy": (
            f"{result.suppressed_duplicates} confirmed re-upload(s) were withheld from ranking. "
            "Within a duplicate family the earliest publication is kept and later copies are "
            "suppressed, so a re-uploader cannot harvest impressions the original creator earned. "
            "Pass include_duplicates=true to see them."
        ),
    }


@router.get("/recommendations/weights", summary="Published ranker weights")
async def weights(container: ContainerDep) -> dict:
    ranking_weights = container.settings.ranking_weights
    return {
        "weights": ranking_weights.as_dict(),
        "sum": round(ranking_weights.total(), 6),
        "mmr_lambda": container.settings.mmr_lambda,
        "freshness_half_life_days": container.settings.freshness_half_life_days,
        "candidate_pool_size": container.settings.candidate_pool_size,
        "signals": {
            "affinity": "cosine between the listener taste vector and the item embedding",
            "co_occurrence": "popularity-normalised item-item co-occurrence over positive baskets",
            "sequence": (
                "first-order transition probability P(next=item | recently finished), "
                "recency-decayed over the listener's last 5 steps. Order-aware, unlike "
                "co-occurrence."
            ),
            "retention": "measured quality score: completion, drop-off, re-engagement, replay",
            "genre_affinity": "learned genre affinity blended with language match",
            "freshness": "exponential decay on publication age",
            "originality": "1 - duplicate risk, so re-uploads do not crowd out original work",
            "exploration": "UCB1-style optimism for under-observed items",
        },
    }
