"""The creator's own view: what is in demand, and how their work is doing.

This is the workflow the brief describes — *"from these logs, this genre has demand
and users don't have this type of content"* — pointed at one signed-in creator
rather than at the platform in aggregate.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount, StorageDep
from app.core.errors import InsufficientDataError
from app.domain.enums import DuplicateKind

router = APIRouter(prefix="/creator", tags=["creator"])


@router.get("/opportunities", summary="What should I write next?")
async def opportunities(
    container: StorageDep,
    account: CurrentAccount,
    limit: int = Query(default=5, ge=1, le=25),
    language: str | None = Query(default=None, description="Restrict to one language."),
) -> dict:
    """Demand gaps ranked for this creator.

    Each row is split into the two things a creator can act on, because they call for
    different work:

      * `write_more`   — demand outruns supply. The audience is there and under-served.
      * `write_better` — demand is met in volume but drop-off is high. More of the same
                         will not help; the existing execution is losing people.

    Segments the creator already publishes in are marked, since extending a shelf you
    already own is a different bet from entering a new one.
    """
    report = await container.insight_repo.latest()
    if report is None:
        raise InsufficientDataError(
            "No demand report yet.",
            details={"hint": "POST /pipeline/run, or GET /insights/demand?refresh=true."},
        )

    mine = await container.content_repo.list_catalog(creator_id=account.user_id, limit=500)
    my_segments = {f"{item.primary_genre}/{item.language}" for item in mine}

    rows = [row for row in report.segments if language is None or row.language == language]

    write_more = [row for row in rows if row.opportunity_score > 0][:limit]
    write_better = sorted(
        (row for row in rows if row.drop_off_rate > 0.4 and row.unique_listeners > 0),
        key=lambda row: row.execution_gap,
        reverse=True,
    )[:limit]

    def render(row) -> dict:
        ratio = (row.demand_share / row.supply_share) if row.supply_share else None
        return {
            "segment": row.segment,
            "genre": row.genre,
            "language": row.language,
            "verdict": _verdict(row, ratio),
            "demand_vs_supply": round(ratio, 2) if ratio else None,
            "opportunity_score": row.opportunity_score,
            "catalog_items": row.catalog_items,
            "unique_listeners": row.unique_listeners,
            "plays": row.plays,
            "completion_rate": row.completion_rate,
            "drop_off_rate": row.drop_off_rate,
            "searches_with_no_results": row.unmet_search_count,
            "confidence": row.confidence.value,
            "sample_size": row.sample_size,
            "you_already_publish_here": row.segment in my_segments,
        }

    return {
        "creator": {"user_id": account.user_id, "display_name": account.display_name},
        "your_segments": sorted(my_segments),
        "write_more": [render(row) for row in write_more],
        "write_better": [render(row) for row in write_better],
        "avoid_patterns": [
            {
                "pattern": row.narrative_pattern,
                "share_of_catalog": row.share_of_catalog,
                "avg_completion_rate": row.avg_completion_rate,
                "listeners_measured": row.listeners,
            }
            for row in report.saturated_patterns
            if row.saturation_index > 1.0
        ][:5],
        "briefs": [brief.model_dump(mode="json") for brief in report.briefs[:limit]],
        "generated_at": report.generated_at.isoformat(),
        "provenance": report.provenance.value,
        "data_notice": report.data_notice,
    }


def _verdict(row, ratio: float | None) -> str:
    if ratio is None:
        return "nothing in the catalog for this segment"
    if row.drop_off_rate > 0.5 and row.opportunity_score <= 0:
        return "audience is here but the existing content loses them — write better, not more"
    if ratio >= 2.0:
        return f"needs much more content ({ratio:.1f}x demand vs supply)"
    if ratio >= 1.15:
        return f"needs more content ({ratio:.1f}x demand vs supply)"
    return "adequately supplied"


@router.get("/performance", summary="How are my own stories doing?")
async def performance(container: StorageDep, account: CurrentAccount) -> dict:
    """Per-story retention for everything this creator has published."""
    mine = await container.content_repo.list_catalog(creator_id=account.user_id, limit=500)
    if not mine:
        return {
            "creator": account.public(),
            "catalog_items": 0,
            "note": "You have not published anything yet. Upload via POST /catalog.",
        }

    content_ids = [item.content_id for item in mine]
    features = await container.features_repo.get_many(content_ids)
    profiles = await container.profile_repo.get_many(content_ids)
    measured = [features[cid] for cid in content_ids if cid in features]

    stories = []
    for item in mine:
        row = features.get(item.content_id)
        profile = profiles.get(item.content_id)
        weakest = (
            min(row.chapter_interest, key=lambda chapter: chapter.interest_score)
            if row and row.chapter_interest
            else None
        )
        stories.append(
            {
                "content_id": item.content_id,
                "title": item.title,
                "segment": f"{item.primary_genre}/{item.language}",
                "listeners": row.unique_listeners if row else 0,
                "completion_rate": row.completion_rate if row else None,
                "drop_off_rate": row.drop_off_rate if row else None,
                "median_abandon_seconds": row.median_abandon_seconds if row else None,
                "confidence": row.confidence.value if row else "no_data",
                "weakest_episode": (
                    {
                        "index": weakest.chapter_index,
                        "title": weakest.title,
                        "interest_score": weakest.interest_score,
                        "drop_offs": weakest.drop_offs,
                    }
                    if weakest
                    else None
                ),
                "originality_score": profile.originality_score if profile else None,
                "duplicate_flag": (
                    profile.duplicate_kind.value
                    if profile and profile.duplicate_kind is not DuplicateKind.NONE
                    else None
                ),
            }
        )

    stories.sort(key=lambda row: (row["listeners"] or 0), reverse=True)
    return {
        "creator": account.public(),
        "catalog_items": len(mine),
        "items_with_listeners": sum(1 for row in measured if row.unique_listeners > 0),
        "total_listeners": sum(row.unique_listeners for row in measured),
        "avg_completion_rate": (
            round(sum(row.completion_rate for row in measured) / len(measured), 4)
            if measured
            else None
        ),
        "stories": stories,
        "note": (
            "Stories with confidence 'no_data' have no logged listening yet — that is "
            "absence of evidence, not evidence of poor performance."
        ),
    }
