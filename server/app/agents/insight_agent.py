"""Agent 3 of 3 — Insight.

Reads the features and profiles the first two agents produced and turns them into
the creator-facing demand report: which (genre, language) cells are under-served,
which narrative patterns are saturated, and what to write next.

The LLM writes the prose. It never chooses the numbers.
"""

from __future__ import annotations

from app.agents.base import Agent, AgentOptions, AgentOutcome
from app.core.config import Settings
from app.core.logging import get_logger
from app.data.repositories import (
    ActivityRepository,
    ContentFeaturesRepository,
    ContentProfileRepository,
    ContentRepository,
    InsightRepository,
)
from app.domain.enums import AgentName
from app.services.demand import DemandService

logger = get_logger(__name__)


class InsightAgent(Agent):
    name = AgentName.INSIGHT

    def __init__(
        self,
        settings: Settings,
        content_repo: ContentRepository,
        activity_repo: ActivityRepository,
        features_repo: ContentFeaturesRepository,
        profiles_repo: ContentProfileRepository,
        insight_repo: InsightRepository,
        demand: DemandService,
    ) -> None:
        self._settings = settings
        self._content_repo = content_repo
        self._activity_repo = activity_repo
        self._features_repo = features_repo
        self._profiles_repo = profiles_repo
        self._insight_repo = insight_repo
        self._demand = demand

    async def execute(self, options: AgentOptions) -> AgentOutcome:
        catalog = await self._content_repo.iter_all(with_transcript=False)
        if not catalog:
            return AgentOutcome(stats={"reason": "empty_catalog"})

        events = await self._activity_repo.stream_all()
        features = await self._features_repo.all_by_id()
        profiles = await self._profiles_repo.all_by_id()

        if not features:
            return AgentOutcome(
                processed=len(catalog),
                stats={"reason": "no_features_yet", "hint": "run the ingestion agent first"},
            )

        report = await self._demand.build_report(
            catalog, events, features, profiles, use_llm=options.use_llm
        )
        await self._insight_repo.save(report)

        opportunities = [row for row in report.segments if row.opportunity_score > 0]
        self._log_demand_verdicts(report, opportunities)
        return AgentOutcome(
            processed=len(catalog),
            written=1,
            stats={
                "segments": len(report.segments),
                "positive_opportunities": len(opportunities),
                "top_segment": opportunities[0].segment if opportunities else None,
                "top_opportunity_score": opportunities[0].opportunity_score if opportunities else None,
                "saturated_patterns": sum(
                    row.saturation_index > 1.0 for row in report.saturated_patterns
                ),
                "briefs": len(report.briefs),
                "brief_source": report.briefs[0].generated_by.value if report.briefs else None,
                "provenance": report.provenance.value,
                "high_confidence_segments": sum(
                    row.confidence.value == "high" for row in report.segments
                ),
            },
        )

    @staticmethod
    def _log_demand_verdicts(report, opportunities: list) -> None:
        """Write the headline finding into the run log.

        The whole point of the system is the sentence "this genre needs more content",
        so it belongs in the pipeline output where anyone watching a run can see it —
        not only in a JSON body someone has to go and fetch.
        """
        if not opportunities:
            logger.info("[demand] No segment is under-served on the current data.")
            return

        logger.info("[demand] --- GENRES THAT NEED MORE CONTENT -------------------")
        for rank, row in enumerate(opportunities[:5], start=1):
            ratio = (row.demand_share / row.supply_share) if row.supply_share else float("inf")
            multiple = f"{ratio:.1f}x" if ratio != float("inf") else "no supply at all"
            logger.info(
                "[demand] %d. %-28s NEEDS MORE CONTENT  "
                "(demand %.1f%% vs supply %.1f%% = %s) "
                "| %d listeners, %d plays, %d searches returned nothing | confidence=%s",
                rank,
                row.segment.upper(),
                row.demand_share * 100,
                row.supply_share * 100,
                multiple,
                row.unique_listeners,
                row.plays,
                row.unmet_search_count,
                row.confidence.value,
            )
        logger.info("[demand] provenance=%s | %s", report.provenance.value, report.data_notice[:110])
