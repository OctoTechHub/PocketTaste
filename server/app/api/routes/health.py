"""Liveness and honest capability reporting."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.domain.enums import Provenance
from app.domain.provenance import notice, resolve_provenance
from app.domain.schemas import HealthResponse
from app.pipelines import databricks

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health and active backends")
async def health(container: ContainerDep) -> HealthResponse:
    mongo_ok = await container.gateway.ping()
    catalog: dict = {"connected": mongo_ok}
    provenance = Provenance.REAL

    if mongo_ok:
        content_count = await container.content_repo.count()
        synthetic = await container.content_repo.count({"is_synthetic": True})
        catalog = {
            "connected": True,
            "database": container.settings.mongo_db_name,
            "content_items": content_count,
            "synthetic_items": synthetic,
            "activity_events": await container.activity_repo.count(),
            "content_profiles": await container.profile_repo.count(),
            "content_features": await container.features_repo.count(),
            "user_profiles": await container.users_repo.count(),
            "pipeline_runs": await container.runs_repo.count(),
            "indexed_documents": container.discovery.indexed_count,
        }
        provenance = resolve_provenance(
            catalog_total=content_count,
            catalog_synthetic=synthetic,
            events_total=catalog["activity_events"],
            events_synthetic=await container.activity_repo.count({"is_synthetic": True}),
        )
        catalog["provenance_notice"] = notice(provenance)

    return HealthResponse(
        status="ok" if mongo_ok else "degraded",
        version=container.settings.app_version,
        environment=container.settings.environment,
        dependencies={
            "mongodb": {"connected": mongo_ok, "required": True},
            "embeddings": container.embeddings.describe(),
            "llm": container.llm.describe(),
            "haystack": container.discovery.describe(),
            "databricks": {
                "configured": container.settings.databricks_enabled,
                "role": "optional batch tier",
            },
            "sarvam": {
                "configured": container.settings.sarvam_enabled,
                "routes_languages": container.settings.sarvam_languages
                if container.settings.sarvam_enabled
                else [],
            },
        },
        catalog=catalog,
        provenance=provenance,
    )


@router.get("/system/architecture", tags=["health"], summary="How the layer is put together")
async def architecture(container: ContainerDep) -> dict:
    return {
        "positioning": (
            "An independent creator-intelligence and discovery layer. It consumes content and "
            "event logs, and produces recommendations, demand analysis and duplicate screening. "
            "It does not replace, wrap or depend on any platform-side recommender."
        ),
        "online_path": {
            "storage": "MongoDB",
            "retrieval": "Haystack AsyncPipeline (BM25 + dense, reciprocal rank fusion)",
            "ranking": "transparent 7-signal linear scorer + MMR re-selection",
            "generation": container.llm.describe(),
        },
        "batch_path": {
            "engine": "Databricks (optional)",
            "configured": container.settings.databricks_enabled,
            "tasks": databricks.describe(container.settings)["tasks"],
        },
        "agents": container.orchestrator.describe(),
        "ranking_weights": container.settings.ranking_weights.as_dict(),
        "similarity_weights": container.settings.similarity_weights.as_dict(),
        "thresholds": {
            "similarity_block": container.settings.similarity_block_threshold,
            "similarity_review": container.settings.similarity_review_threshold,
            "cluster": container.settings.cluster_threshold,
            "mmr_lambda": container.settings.mmr_lambda,
            "freshness_half_life_days": container.settings.freshness_half_life_days,
            "min_confident_sample_size": container.settings.min_confident_sample_size,
        },
        "excluded_by_design": [
            "no model fine-tuning — the log is far too small to justify it",
            "no trained ranker — an unexplainable score is useless to a creator",
            "no claim to beat a production recommender trained on years of data",
            "no synthetic figure is ever presented as real audience truth",
        ],
    }
