"""Creator-facing demand intelligence."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import StorageDep
from app.core.errors import InsufficientDataError

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/demand", summary="Supply/demand gap by genre and language")
async def demand(
    container: StorageDep,
    refresh: bool = Query(default=False, description="Recompute instead of returning the stored report."),
    use_llm: bool = Query(default=True),
) -> dict:
    """Returns the latest stored report by default. `refresh=true` recomputes from
    the current event log without running the whole pipeline."""
    if not refresh:
        stored = await container.insight_repo.latest()
        if stored is not None:
            return stored.model_dump(mode="json") | {"source": "stored"}

    catalog = await container.content_repo.iter_all(with_transcript=False)
    if not catalog:
        raise InsufficientDataError(
            "Catalog is empty, so no demand can be measured.",
            details={"hint": "Load content via POST /catalog or scripts/seed.py."},
        )
    features = await container.features_repo.all_by_id()
    if not features:
        raise InsufficientDataError(
            "No behavioural features have been computed yet.",
            details={"hint": "POST /pipeline/run to build them from the current event log."},
        )

    events = await container.activity_repo.stream_all()
    profiles = await container.profile_repo.all_by_id()
    report = await container.demand.build_report(
        catalog, events, features, profiles, use_llm=use_llm and container.llm.available
    )
    await container.insight_repo.save(report)
    return report.model_dump(mode="json") | {"source": "recomputed"}


@router.get("/opportunities", summary="Under-served segments only")
async def opportunities(
    container: StorageDep,
    limit: int = Query(default=10, ge=1, le=50),
    min_confidence: str = Query(default="low", pattern="^(low|medium|high)$"),
) -> dict:
    report = await container.insight_repo.latest()
    if report is None:
        raise InsufficientDataError(
            "No demand report has been generated yet.",
            details={"hint": "POST /pipeline/run, or GET /insights/demand?refresh=true."},
        )
    ranking = {"low": 0, "medium": 1, "high": 2}
    threshold = ranking[min_confidence]
    rows = [
        row
        for row in report.segments
        if row.opportunity_score > 0 and ranking[row.confidence.value] >= threshold
    ][:limit]
    return {
        "generated_at": report.generated_at.isoformat(),
        "provenance": report.provenance.value,
        "data_notice": report.data_notice,
        "opportunities": [row.model_dump(mode="json") for row in rows],
        "briefs": [
            brief.model_dump(mode="json")
            for brief in report.briefs
            if brief.segment in {row.segment for row in rows}
        ],
        "formula": (
            "opportunity_score = (demand_share - supply_share) * (1 - duplicate_density). "
            "Positive means the cell absorbs more attention than its share of the catalog."
        ),
    }


@router.get("/saturation", summary="Over-supplied narrative patterns")
async def saturation(container: StorageDep) -> dict:
    report = await container.insight_repo.latest()
    if report is None:
        raise InsufficientDataError(
            "No demand report has been generated yet.",
            details={"hint": "POST /pipeline/run first."},
        )
    return {
        "generated_at": report.generated_at.isoformat(),
        "provenance": report.provenance.value,
        "patterns": [row.model_dump(mode="json") for row in report.saturated_patterns],
        "formula": (
            "saturation_index = share_of_catalog / avg_completion_rate. Above 1.0 means the "
            "pattern occupies more catalog than its retention justifies."
        ),
    }


@router.get("/briefs", summary="Evidence-backed content briefs")
async def briefs(container: StorageDep) -> dict:
    report = await container.insight_repo.latest()
    if report is None:
        raise InsufficientDataError(
            "No demand report has been generated yet.", details={"hint": "POST /pipeline/run first."}
        )
    return {
        "generated_at": report.generated_at.isoformat(),
        "provenance": report.provenance.value,
        "data_notice": report.data_notice,
        "briefs": [brief.model_dump(mode="json") for brief in report.briefs],
        "grounding": (
            "Brief prose is written by the LLM from the supporting_metrics attached to each brief. "
            "The LLM is instructed to cite only those numbers; generated_by records whether a "
            "brief came from the model or the deterministic fallback."
        ),
    }
