"""Agent pipeline control and the optional Databricks batch tier."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.agents.base import AgentOptions
from app.api.deps import ContainerDep, StorageDep
from app.core.errors import NotFoundError
from app.domain.schemas import PipelineRunRequest
from app.pipelines import databricks

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run", summary="Run the three-agent pipeline")
async def run(payload: PipelineRunRequest, container: StorageDep) -> dict:
    """Sequential and idempotent. A failed stage does not abort the run; the result
    is marked `partial` and the failing stage carries its error."""
    stages = container.orchestrator.resolve_stages(payload.stages)
    result = await container.orchestrator.run(
        AgentOptions(
            force_relabel=payload.force_relabel,
            use_llm=payload.use_llm and container.llm.available,
        ),
        stages,
    )
    return result.model_dump(mode="json") | {
        "llm_used": payload.use_llm and container.llm.available,
        "embedding_backend": container.embeddings.backend,
    }


@router.get("/runs", summary="Recent pipeline runs")
async def runs(container: StorageDep, limit: int = Query(default=10, ge=1, le=100)) -> dict:
    recent = await container.runs_repo.recent(limit=limit)
    return {
        "total_runs": await container.runs_repo.count(),
        "runs": [run.model_dump(mode="json") for run in recent],
    }


@router.get("/runs/{run_id}", summary="One pipeline run")
async def run_detail(run_id: str, container: StorageDep) -> dict:
    result = await container.runs_repo.get(run_id)
    if result is None:
        raise NotFoundError(f"No pipeline run with id '{run_id}'.")
    return result.model_dump(mode="json")


@router.get("/describe", summary="Agent roster and stage ordering")
async def describe(container: ContainerDep) -> dict:
    return container.orchestrator.describe() | {
        "agent_count_rationale": (
            "Three agents, one per stage. Each has a single reason to fail and a single owner of "
            "its output. Splitting further would add coordination surface without adding capability."
        ),
        "llm_available": container.llm.available,
        "embedding_backend": container.embeddings.backend,
    }


@router.get("/scheduler", summary="Background pipeline status and cost")
async def scheduler_status(container: ContainerDep) -> dict:
    """The loop runs ingestion + insight only, with the LLM off, and skips entirely
    when no new events have arrived — so an idle deployment spends nothing."""
    return container.scheduler.describe()


@router.post("/scheduler/tick", summary="Run one scheduler beat now")
async def scheduler_tick(
    container: StorageDep,
    force: bool = Query(default=False, description="Run even if no new events arrived."),
) -> dict:
    """Useful for testing the loop without waiting for the interval."""
    return await container.scheduler.tick(force=force)


@router.post("/scheduler/stop", summary="Stop the background loop")
async def scheduler_stop(container: ContainerDep) -> dict:
    await container.scheduler.stop()
    container.scheduler.state.enabled = False
    return {"stopped": True} | container.scheduler.describe()


@router.post("/scheduler/start", summary="Start the background loop")
async def scheduler_start(container: ContainerDep) -> dict:
    container.settings.background_pipeline_enabled = True
    await container.scheduler.start()
    return {"started": True} | container.scheduler.describe()


@router.get("/databricks", summary="Batch-tier job specification")
async def databricks_spec(container: ContainerDep) -> dict:
    return databricks.describe(container.settings)


@router.post("/cache/invalidate", summary="Force the serving cache to reload")
async def invalidate(container: StorageDep) -> dict:
    container.cache.invalidate()
    context = await container.cache.get(force=True)
    return {
        "reloaded": True,
        "catalog_items": len(context.catalog),
        "profiles": len(context.profiles),
        "feature_rows": len(context.features),
        "co_occurrence_nodes": len(context.co_occurrence),
        "total_plays": context.total_plays,
        "provenance": context.provenance.value,
    }
