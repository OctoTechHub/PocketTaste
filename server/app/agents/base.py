"""Agent contract.

Three agents, deliberately. Each owns one stage of the pipeline, has one reason to
fail, and reports what it processed. More agents would mean more coordination
surface for no extra capability.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.domain.enums import AgentName, RunStatus
from app.domain.models import AgentRun

logger = get_logger(__name__)


@dataclass(slots=True)
class AgentOptions:
    force_relabel: bool = False
    use_llm: bool = True
    limit: int | None = None


@dataclass(slots=True)
class AgentOutcome:
    processed: int = 0
    written: int = 0
    skipped: int = 0
    stats: dict = field(default_factory=dict)


class Agent(abc.ABC):
    """Base class handling timing, status and error capture identically for all agents."""

    name: AgentName

    @abc.abstractmethod
    async def execute(self, options: AgentOptions) -> AgentOutcome:
        """Do the work. Raise on failure; the wrapper records it."""

    async def run(self, run_id: str, options: AgentOptions) -> AgentRun:
        started = utcnow()
        logger.info("[%s] starting (run=%s)", self.name.value, run_id)
        try:
            outcome = await self.execute(options)
            status = RunStatus.SUCCEEDED
            error = None
        except Exception as exc:  # noqa: BLE001 - the run record is the error channel
            logger.exception("[%s] failed", self.name.value)
            outcome, status, error = AgentOutcome(), RunStatus.FAILED, f"{type(exc).__name__}: {exc}"[:500]

        finished = utcnow()
        duration_ms = int((finished - started).total_seconds() * 1000)
        logger.info(
            "[%s] %s in %dms (processed=%d written=%d skipped=%d)",
            self.name.value,
            status.value,
            duration_ms,
            outcome.processed,
            outcome.written,
            outcome.skipped,
        )
        return AgentRun(
            run_id=run_id,
            agent=self.name,
            status=status,
            started_at=started,
            finished_at=finished,
            duration_ms=duration_ms,
            processed=outcome.processed,
            written=outcome.written,
            skipped=outcome.skipped,
            stats=outcome.stats,
            error=error,
        )
