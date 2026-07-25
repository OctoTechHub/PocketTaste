"""Liveness and honest capability reporting."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.domain.enums import Provenance
from app.domain.provenance import notice, resolve_provenance
from app.domain.schemas import HealthResponse
from app.pipelines import databricks

router = APIRouter(tags=["health"])


@router.get("/", tags=["health"], summary="API index — every route, grouped by purpose")
async def index(container: ContainerDep) -> dict:
    """A map of the API, so callers do not have to read the OpenAPI schema to find
    the four or five endpoints they actually need."""
    return {
        "service": container.settings.app_name,
        "version": container.settings.app_version,
        "docs": "/docs",
        "start_here": [
            "POST /auth/login              -> bearer token",
            "POST /activity                -> log listening (authenticated)",
            "POST /pipeline/run            -> build features and insights",
            "POST /me/recommendations      -> personalised results",
            "GET  /creator/opportunities   -> which genres need more content",
        ],
        "routes": {
            "auth": {
                "POST /auth/register": "create an account",
                "POST /auth/login": "sign in, get a bearer token",
                "GET /auth/me": "the signed-in account",
                "GET /auth/scheme": "how auth is configured",
            },
            "listener": {
                "POST /activity": "log one event (user comes from the token)",
                "POST /activity/batch": "log up to 5000",
                "GET /activity/schema": "event types and interaction weights",
                "GET /activity/stats": "log volume, real vs simulated",
                "POST /me/recommendations": "recommendations for the token holder",
                "GET /me/profile": "your derived taste profile",
                "GET /me/history": "your own event log",
            },
            "recommendations": {
                "POST /recommendations": "rank for any user id",
                "GET /recommendations/weights": "published signal weights",
                "POST /discovery/search": "natural-language search (hybrid retrieval)",
                "GET /discovery/pipeline": "retrieval topology",
                "POST /discovery/reindex": "rebuild the search index",
            },
            "creator": {
                "GET /creator/opportunities": "what to write next: write_more vs write_better",
                "GET /creator/performance": "how your own stories retain",
                "POST /catalog": "upload a story (screened before storing)",
                "POST /copilot/outline": "GOAT outline, screened and demand-anchored",
                "POST /copilot/draft": "GOAT outline plus written scene text",
                "GET /copilot/engine": "which outlining engine is active",
            },
            "originality": {
                "POST /similarity/check": "screen a draft against the catalog",
                "GET /similarity/duplicates": "duplicate families already in the catalog",
                "GET /similarity/audit": "recent screening decisions",
            },
            "insights": {
                "GET /insights/demand": "supply/demand by genre and language",
                "GET /insights/opportunities": "under-served segments only",
                "GET /insights/saturation": "over-used narrative patterns",
                "GET /insights/briefs": "evidence-backed content briefs",
                "GET /analytics/content/{id}": "retention curve and episode interest",
                "GET /analytics/content/{id}/drop-off": "plain-English drop-off diagnosis",
                "GET /analytics/user/{id}": "one listener's derived profile",
                "GET /analytics/creators/{id}": "one creator's portfolio",
            },
            "pipeline": {
                "POST /pipeline/run": "run the three agents",
                "GET /pipeline/runs": "run history",
                "GET /pipeline/describe": "agent roster and stage ordering",
                "GET /pipeline/scheduler": "background loop status and cost",
                "POST /pipeline/scheduler/tick": "run one beat now",
                "GET /pipeline/databricks": "batch-tier job specification",
                "POST /evaluation/run": "Recall@K / NDCG@K vs baselines",
                "GET /evaluation/method": "how the evaluation is set up",
            },
            "system": {
                "GET /health": "status and active backends",
                "GET /system/architecture": "weights, thresholds, what is excluded by design",
            },
        },
    }


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
