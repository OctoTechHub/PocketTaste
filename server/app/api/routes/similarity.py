"""Pre-upload duplicate screening and the audit trail behind it."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import StorageDep
from app.domain.enums import DuplicateKind
from app.domain.models import Chapter
from app.domain.schemas import SimilarityCheckRequest
from app.services.similarity import SimilarityCandidate

router = APIRouter(prefix="/similarity", tags=["similarity"])


@router.post("/check", summary="Screen a draft against the catalog before upload")
async def check(payload: SimilarityCheckRequest, container: StorageDep) -> dict:
    """Six independent signals, each reported separately. `block` means a human must
    look at it — it is not an automated plagiarism ruling."""
    query = f"{payload.title}\n{payload.description}\n{payload.transcript[:3000]}"
    shortlist_ids = await container.discovery.shortlist_for_similarity(
        query, top_k=25, exclude_content_id=payload.exclude_content_id
    )
    catalog = (
        await container.content_repo.get_many(shortlist_ids, with_transcript=True)
        if shortlist_ids
        else await container.content_repo.iter_all(with_transcript=True)
    )
    profiles = await container.profile_repo.get_many([item.content_id for item in catalog])

    report = await container.similarity.screen(
        SimilarityCandidate(
            title=payload.title,
            description=payload.description,
            transcript=payload.transcript or payload.description,
            language=payload.language,
            genres=payload.genres,
            chapters=[Chapter.model_validate(chapter.model_dump()) for chapter in payload.chapters],
        ),
        catalog,
        profiles,
        top_k=payload.top_k,
        exclude_content_id=payload.exclude_content_id,
        use_llm=payload.use_llm and container.llm.available,
    )
    await container.similarity_audit_repo.record(report, creator_id="preflight", context="preflight_check")

    return report.model_dump(mode="json") | {
        "shortlist_source": "haystack_hybrid_retrieval" if shortlist_ids else "full_catalog_scan",
        "signal_reference": {
            "narrative_arc": "story-skeleton match; survives paraphrasing and renamed characters",
            "semantic": "surface meaning match over title, description, tags and transcript",
            "lexical_shingle": "Jaccard over 5-word sequences; detects verbatim copy-paste",
            "title": "1.0 when titles are identical after stripping season/part/language markers",
            "description": "token overlap of the blurbs",
            "chapter_structure": "episode count and relative chapter-length profile",
        },
    }


@router.get("/duplicates", summary="Duplicate families already in the catalog")
async def duplicates(
    container: StorageDep,
    min_risk: float = Query(default=0.6, ge=0.0, le=1.0),
) -> dict:
    profiles = await container.profile_repo.all_by_id()
    flagged = [
        profile
        for profile in profiles.values()
        if profile.duplicate_kind is not DuplicateKind.NONE or profile.duplicate_risk >= min_risk
    ]
    flagged.sort(key=lambda profile: profile.duplicate_risk, reverse=True)
    items = await container.content_repo.get_many([profile.content_id for profile in flagged])
    titles = {item.content_id: item for item in items}

    clusters: dict[str, list[dict]] = {}
    for profile in flagged:
        item = titles.get(profile.content_id)
        clusters.setdefault(profile.cluster_id or "unclustered", []).append(
            {
                "content_id": profile.content_id,
                "title": item.title if item else None,
                "creator_id": item.creator_id if item else None,
                "duplicate_risk": profile.duplicate_risk,
                "originality_score": profile.originality_score,
                "duplicate_kind": profile.duplicate_kind.value,
                "nearest_neighbours": profile.nearest_neighbours,
            }
        )

    return {
        "flagged_items": len(flagged),
        "profiles_scanned": len(profiles),
        "clusters": clusters,
        "note": (
            "Flags come from the nightly originality sweep, which compares each item against a "
            "retrieved shortlist rather than the whole catalog. Re-run POST /pipeline/run to refresh."
        ),
    }


@router.get("/audit", summary="Recent screening decisions")
async def audit(container: StorageDep, limit: int = Query(default=25, ge=1, le=200)) -> dict:
    records = await container.similarity_audit_repo.recent(limit=limit)
    return {
        "total_recorded": await container.similarity_audit_repo.count(),
        "returned": len(records),
        "records": records,
    }
