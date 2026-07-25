"""Offline accuracy measurement."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import StorageDep
from app.core.errors import InsufficientDataError
from app.domain.schemas import EvaluationRequest

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", summary="Temporal-holdout evaluation against two baselines")
async def run(payload: EvaluationRequest, container: StorageDep) -> dict:
    """Recall@K, NDCG@K, MRR, coverage, novelty and intra-list diversity for the
    hybrid ranker, the popularity baseline and a random baseline."""
    catalog = await container.content_repo.iter_all(with_transcript=False)
    if len(catalog) < payload.k:
        raise InsufficientDataError(
            f"Catalog has {len(catalog)} items, fewer than k={payload.k}.",
            details={"hint": "Load more content or lower k."},
        )
    events = await container.activity_repo.stream_all()
    if len(events) < 20:
        raise InsufficientDataError(
            f"Only {len(events)} events logged; a temporal split needs materially more.",
            details={"hint": "Run scripts/seed.py or log real activity."},
        )
    profiles = await container.profile_repo.all_by_id()

    report = container.evaluation.evaluate(
        catalog,
        events,
        profiles,
        k=payload.k,
        max_users=payload.max_users,
        min_interactions=payload.min_interactions,
    )
    return report.as_dict()


@router.get("/method", summary="How the evaluation is set up and why")
async def method() -> dict:
    return {
        "protocol": "global temporal holdout at 80% of the event stream",
        "why_not_random_leave_one_out": (
            "Random leave-one-out leaks the future into the features. A content item's completion "
            "rate computed over the whole log already encodes the interaction being predicted, "
            "which inflates Recall@K. A temporal split reproduces the real serving condition."
        ),
        "rebuilt_from_train_slice_only": [
            "user taste vectors and affinities",
            "content behavioural features (retention, quality score, plays)",
            "item-item co-occurrence matrix",
        ],
        "shared_across_slices": [
            "content embeddings — derived from story text, not behaviour, so they carry no "
            "post-split information"
        ],
        "ground_truth": "positive interactions (complete, replay, revisit, resume) after the split",
        "baselines": {
            "popularity": "rank by training-set play count; a genuinely strong baseline",
            "random": "seeded uniform sample; the floor",
        },
        "metrics": {
            "recall_at_k": "share of a user's held-out positives that appear in the top K",
            "precision_at_k": "share of the top K that were held-out positives",
            "ndcg_at_k": "rank-discounted gain, binary relevance",
            "mrr": "reciprocal rank of the first hit",
            "hit_rate": "share of users with at least one hit",
            "catalog_coverage": "distinct items recommended across all users / catalog size",
            "novelty": "mean -log2(item play share); higher means less obvious picks",
            "intra_list_diversity": "1 - mean pairwise cosine within each returned list",
        },
        "honesty_note": (
            "On synthetic data these numbers verify that the pipeline computes correctly. They "
            "are not evidence of real-world accuracy, and the report says so in its caveats."
        ),
    }
