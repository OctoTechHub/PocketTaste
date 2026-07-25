"""Pipeline orchestrator.

Deterministic, sequential, and boring on purpose. The stage order is fixed by data
dependency, not by preference:

    content_intelligence -> ingestion -> insight

Content Intelligence must run first because user taste vectors are weighted means
of content embeddings. Ingestion must run before Insight because demand segments
are computed from behavioural features. A failed stage does not abort the run —
later stages still execute on whatever is already persisted, and the run is marked
`partial` so the failure is visible rather than silent.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.agents.base import Agent, AgentOptions
from app.agents.content_intelligence_agent import ContentIntelligenceAgent
from app.agents.ingestion_agent import IngestionAgent
from app.agents.insight_agent import InsightAgent
from app.core.clock import utcnow
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.data.repositories import PipelineRunRepository
from app.domain.enums import AgentName, RunStatus
from app.domain.models import PipelineRun
from app.services.context_cache import RankingContextCache

logger = get_logger(__name__)

DEFAULT_STAGE_ORDER: tuple[AgentName, ...] = (
    AgentName.CONTENT_INTELLIGENCE,
    AgentName.INGESTION,
    AgentName.INSIGHT,
)


class PipelineOrchestrator:
    def __init__(
        self,
        content_intelligence: ContentIntelligenceAgent,
        ingestion: IngestionAgent,
        insight: InsightAgent,
        runs_repo: PipelineRunRepository,
        cache: RankingContextCache,
    ) -> None:
        self._agents: dict[AgentName, Agent] = {
            AgentName.CONTENT_INTELLIGENCE: content_intelligence,
            AgentName.INGESTION: ingestion,
            AgentName.INSIGHT: insight,
        }
        self._runs_repo = runs_repo
        self._cache = cache
        self._lock = asyncio.Lock()

    def describe(self) -> dict:
        return {
            "stages": [
                {
                    "order": index + 1,
                    "agent": name.value,
                    "purpose": _PURPOSE[name],
                    "uses_llm": name is not AgentName.INGESTION,
                }
                for index, name in enumerate(DEFAULT_STAGE_ORDER)
            ],
            "stage_order_reason": (
                "content_intelligence produces the embeddings that ingestion needs for taste "
                "vectors; ingestion produces the features that insight aggregates."
            ),
            "concurrency": "sequential — each stage consumes the previous stage's output",
        }

    def resolve_stages(self, requested: list[str] | None) -> list[AgentName]:
        if not requested:
            return list(DEFAULT_STAGE_ORDER)
        valid = {name.value: name for name in AgentName}
        resolved: list[AgentName] = []
        for stage in requested:
            key = stage.strip().lower()
            if key not in valid:
                raise ValidationError(
                    f"Unknown stage '{stage}'.", details={"valid_stages": sorted(valid)}
                )
            resolved.append(valid[key])
        return resolved

    async def run(self, options: AgentOptions, stages: list[AgentName] | None = None) -> PipelineRun:
        """Run the pipeline. Concurrent invocations are serialised, not queued twice."""
        if self._lock.locked():
            raise ValidationError("A pipeline run is already in progress.")

        async with self._lock:
            run_id = f"run_{uuid4().hex[:12]}"
            started = utcnow()
            ordered = stages or list(DEFAULT_STAGE_ORDER)
            logger.info("Pipeline %s starting: %s", run_id, [stage.value for stage in ordered])

            results = []
            for stage in ordered:
                results.append(await self._agents[stage].run(run_id, options))

            failures = [result for result in results if result.status is RunStatus.FAILED]
            if not failures:
                status = RunStatus.SUCCEEDED
            elif len(failures) == len(results):
                status = RunStatus.FAILED
            else:
                status = RunStatus.PARTIAL

            finished = utcnow()
            run = PipelineRun(
                run_id=run_id,
                status=status,
                started_at=started,
                finished_at=finished,
                duration_ms=int((finished - started).total_seconds() * 1000),
                stages=results,
                error="; ".join(
                    f"{result.agent}: {result.error}" for result in failures if result.error
                )
                or None,
            )
            await self._runs_repo.upsert(run)

            # Serving cache is now stale by definition.
            self._cache.invalidate()
            logger.info("Pipeline %s finished: %s in %dms", run_id, status.value, run.duration_ms)
            return run


_PURPOSE: dict[AgentName, str] = {
    AgentName.CONTENT_INTELLIGENCE: (
        "Embeds and labels the catalog, clusters it on narrative arc, scores originality "
        "and duplicate risk, and rebuilds the Haystack retrieval index."
    ),
    AgentName.INGESTION: (
        "Converts the raw event log into deterministic behavioural features: retention "
        "curves, chapter interest, abandon points and per-listener taste vectors."
    ),
    AgentName.INSIGHT: (
        "Aggregates features into (genre, language) demand segments, flags saturated "
        "narrative patterns and writes evidence-backed creator briefs."
    ),
}
