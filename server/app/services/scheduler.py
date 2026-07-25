"""Continuous background pipeline, with zero API spend by default.

The pipeline is batch by nature: profiles are rebuilt from the log rather than
updated per event. Making a human remember to trigger it is a bad design, so this
runs it on a loop.

**How it costs nothing.** Two rules:

1. `use_llm=False`. The only stages that run are `ingestion` and `insight`, and
   both are pure computation over data already in Mongo. The insight agent falls
   back to its deterministic brief writer, which is disclosed as `heuristic` in the
   output exactly as it always is.
2. **Skip when nothing changed.** Before each tick the loop compares the current
   event count against the count at the last run. No new events means no new
   features, so it does nothing at all. An idle deployment performs one cheap
   `count_documents` per interval and stops there.

Content intelligence — the stage that embeds and labels, and therefore the only one
that spends money — is deliberately excluded. New uploads are profiled on demand,
or by an explicit `POST /pipeline/run`, or by the Databricks batch tier. A loop
should never be able to run up a bill on its own.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from app.agents.base import AgentOptions
from app.agents.orchestrator import PipelineOrchestrator
from app.core.clock import utcnow
from app.core.config import Settings
from app.core.logging import get_logger
from app.data.repositories import ActivityRepository
from app.domain.enums import AgentName

logger = get_logger(__name__)

#: Stages safe to run unattended. Excludes content_intelligence, which spends money.
BACKGROUND_STAGES = [AgentName.INGESTION, AgentName.INSIGHT]


@dataclass(slots=True)
class SchedulerState:
    enabled: bool = False
    running: bool = False
    interval_seconds: int = 900
    ticks: int = 0
    runs_executed: int = 0
    runs_skipped: int = 0
    last_tick_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_id: str | None = None
    last_status: str | None = None
    last_duration_ms: int = 0
    last_skip_reason: str | None = None
    last_error: str | None = None
    events_at_last_run: int = -1
    history: list[dict] = field(default_factory=list)


class PipelineScheduler:
    def __init__(
        self,
        settings: Settings,
        orchestrator: PipelineOrchestrator,
        activity_repo: ActivityRepository,
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        self._activity_repo = activity_repo
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.state = SchedulerState(
            enabled=settings.background_pipeline_enabled,
            interval_seconds=settings.background_pipeline_seconds,
        )

    # --- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        if not self._settings.background_pipeline_enabled:
            logger.info(
                "Background pipeline disabled. Set BACKGROUND_PIPELINE_ENABLED=true to run it."
            )
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self.state.enabled = True
        self._task = asyncio.create_task(self._loop(), name="pipeline-scheduler")
        logger.info(
            "Background pipeline every %ds (stages=%s, llm=%s -> no API spend)",
            self.state.interval_seconds,
            [stage.value for stage in BACKGROUND_STAGES],
            self._settings.background_pipeline_use_llm,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutting down
                pass
        self.state.running = False

    # --- loop ---------------------------------------------------------------

    async def _loop(self) -> None:
        # A short initial delay lets startup finish before the first tick.
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=self._settings.background_pipeline_delay)
            return
        except asyncio.TimeoutError:
            pass

        while not self._stop.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - a bad tick must not kill the loop
                self.state.last_error = f"{type(exc).__name__}: {exc}"[:300]
                logger.exception("Background pipeline tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.state.interval_seconds)
                return
            except asyncio.TimeoutError:
                continue

    async def tick(self, *, force: bool = False) -> dict:
        """One scheduler beat. Returns what it decided and why."""
        self.state.ticks += 1
        self.state.last_tick_at = utcnow()

        event_count = await self._activity_repo.count()
        if not force and event_count == self.state.events_at_last_run:
            self.state.runs_skipped += 1
            self.state.last_skip_reason = f"no new events since last run ({event_count})"
            logger.debug("Background pipeline skipped: %s", self.state.last_skip_reason)
            return {"ran": False, "reason": self.state.last_skip_reason, "events": event_count}

        if not force and event_count == 0:
            self.state.runs_skipped += 1
            self.state.last_skip_reason = "no activity logged yet"
            return {"ran": False, "reason": self.state.last_skip_reason, "events": 0}

        self.state.running = True
        try:
            run = await self._orchestrator.run(
                AgentOptions(use_llm=self._settings.background_pipeline_use_llm),
                list(BACKGROUND_STAGES),
            )
        finally:
            self.state.running = False

        self.state.runs_executed += 1
        self.state.last_run_at = utcnow()
        self.state.last_run_id = run.run_id
        self.state.last_status = run.status.value
        self.state.last_duration_ms = run.duration_ms
        self.state.last_skip_reason = None
        self.state.events_at_last_run = event_count
        self.state.history = (
            self.state.history
            + [
                {
                    "run_id": run.run_id,
                    "status": run.status.value,
                    "duration_ms": run.duration_ms,
                    "events": event_count,
                    "at": self.state.last_run_at.isoformat(),
                }
            ]
        )[-20:]

        logger.info(
            "Background pipeline %s in %dms over %d events (run=%s)",
            run.status.value,
            run.duration_ms,
            event_count,
            run.run_id,
        )
        return {"ran": True, "run_id": run.run_id, "status": run.status.value, "events": event_count}

    # --- introspection ------------------------------------------------------

    def describe(self) -> dict:
        return {
            "enabled": self.state.enabled,
            "alive": bool(self._task and not self._task.done()),
            "currently_running": self.state.running,
            "interval_seconds": self.state.interval_seconds,
            "stages": [stage.value for stage in BACKGROUND_STAGES],
            "uses_llm": self._settings.background_pipeline_use_llm,
            "api_cost": (
                "none — LLM disabled and content_intelligence excluded, so no embedding "
                "or completion calls are made"
                if not self._settings.background_pipeline_use_llm
                else "LLM ENABLED for background runs; this will spend API credits"
            ),
            "ticks": self.state.ticks,
            "runs_executed": self.state.runs_executed,
            "runs_skipped_no_new_events": self.state.runs_skipped,
            "last_tick_at": self.state.last_tick_at,
            "last_run_at": self.state.last_run_at,
            "last_run_id": self.state.last_run_id,
            "last_status": self.state.last_status,
            "last_duration_ms": self.state.last_duration_ms,
            "last_skip_reason": self.state.last_skip_reason,
            "last_error": self.state.last_error,
            "recent_runs": self.state.history[-5:],
            "excluded_stage": {
                "agent": AgentName.CONTENT_INTELLIGENCE.value,
                "why": (
                    "It embeds and labels content, which costs money per item. New uploads "
                    "are profiled by an explicit POST /pipeline/run or by the Databricks "
                    "batch tier — never by an unattended loop."
                ),
            },
        }
