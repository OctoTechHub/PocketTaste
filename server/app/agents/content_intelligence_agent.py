"""Agent 2 of 3 — Content Intelligence.

Runs FIRST in the pipeline despite being the second layer conceptually: taste
vectors are built from content embeddings, so the embeddings must exist before the
Ingestion Agent can profile a listener.

Responsibilities:
  * embed each catalog item (surface + narrative arc)
  * label themes/tone/tropes/pattern/pacing (LLM, heuristic fallback)
  * cluster the catalog on the arc embedding
  * score originality and duplicate risk against nearest neighbours
  * rebuild the Haystack retrieval index
"""

from __future__ import annotations

import asyncio
from collections import Counter

from app.agents.base import Agent, AgentOptions, AgentOutcome
from app.core.clock import as_utc
from app.core.config import Settings
from app.core.logging import get_logger
from app.data.repositories import ContentProfileRepository, ContentRepository
from app.domain.enums import AgentName, DuplicateKind
from app.domain.models import ContentItem, ContentProfile
from app.services.content_intelligence import ContentIntelligenceService
from app.services.discovery import DiscoveryService
from app.services.similarity import SimilarityService

logger = get_logger(__name__)

_ANALYSIS_CONCURRENCY = 6
_NEIGHBOUR_SHORTLIST = 12


class ContentIntelligenceAgent(Agent):
    name = AgentName.CONTENT_INTELLIGENCE

    def __init__(
        self,
        settings: Settings,
        content_repo: ContentRepository,
        profile_repo: ContentProfileRepository,
        intelligence: ContentIntelligenceService,
        similarity: SimilarityService,
        discovery: DiscoveryService,
    ) -> None:
        self._settings = settings
        self._content_repo = content_repo
        self._profile_repo = profile_repo
        self._intelligence = intelligence
        self._similarity = similarity
        self._discovery = discovery

    async def execute(self, options: AgentOptions) -> AgentOutcome:
        catalog = await self._content_repo.iter_all(with_transcript=True)
        if not catalog:
            return AgentOutcome(stats={"reason": "empty_catalog"})

        existing = await self._profile_repo.all_by_id()
        stale = [item for item in catalog if self._needs_profiling(item, existing, options)]
        logger.info("Profiling %d/%d catalog items", len(stale), len(catalog))

        fresh = await self._analyse_many(stale, use_llm=options.use_llm)
        profiles = {**existing, **{profile.content_id: profile for profile in fresh}}

        # Cluster the whole catalog every run — a single new item can merge two clusters.
        clustered = self._intelligence.cluster(list(profiles.values()))

        # Index before neighbour scoring so the shortlist uses current embeddings.
        self._discovery.index(catalog, clustered)
        duplicates = await self._score_originality(catalog, clustered)

        written = await self._profile_repo.upsert_many(list(clustered.values()))
        label_sources = Counter(profile.label_source.value for profile in clustered.values())

        return AgentOutcome(
            processed=len(catalog),
            written=written,
            skipped=len(catalog) - len(stale),
            stats={
                "profiles_generated": len(fresh),
                "profiles_total": len(clustered),
                "clusters": len({profile.cluster_id for profile in clustered.values()}),
                "duplicate_flags": duplicates,
                "label_sources": dict(label_sources),
                "embedding_backend": self._intelligence.embedding_backend,
                "indexed_documents": self._discovery.indexed_count,
            },
        )

    @staticmethod
    def _needs_profiling(
        item: ContentItem, existing: dict[str, ContentProfile], options: AgentOptions
    ) -> bool:
        if options.force_relabel:
            return True
        profile = existing.get(item.content_id)
        if profile is None or not profile.embedding:
            return True
        # Re-profile when the item was edited after its profile was computed.
        return as_utc(item.created_at) > as_utc(profile.computed_at)

    async def _analyse_many(self, items: list[ContentItem], *, use_llm: bool) -> list[ContentProfile]:
        if not items:
            return []
        semaphore = asyncio.Semaphore(_ANALYSIS_CONCURRENCY)

        async def _one(item: ContentItem) -> ContentProfile | None:
            async with semaphore:
                try:
                    return await self._intelligence.analyse(item, use_llm=use_llm)
                except Exception:  # noqa: BLE001 - one bad item must not kill the batch
                    logger.exception("Profiling failed for %s", item.content_id)
                    return None

        results = await asyncio.gather(*(_one(item) for item in items))
        return [profile for profile in results if profile is not None]

    async def _score_originality(
        self, catalog: list[ContentItem], profiles: dict[str, ContentProfile]
    ) -> dict[str, int]:
        """Score every item against a retrieved shortlist rather than the full catalog.

        Full pairwise comparison is O(n^2) with expensive shingle sets. Retrieval
        narrows each item to its plausible matches first — this is the scaling
        argument for keeping Haystack in the loop.
        """
        by_id = {item.content_id: item for item in catalog}
        flags: Counter[str] = Counter()

        for item in catalog:
            profile = profiles.get(item.content_id)
            if profile is None:
                continue
            shortlist_ids = await self._discovery.shortlist_for_similarity(
                item.searchable_text(), top_k=_NEIGHBOUR_SHORTLIST, exclude_content_id=item.content_id
            )
            shortlist = [by_id[cid] for cid in shortlist_ids if cid in by_id]
            if not shortlist:
                continue
            matches = self._similarity.compare_all(
                item, profile, shortlist, profiles, exclude_content_id=item.content_id
            )
            matches.sort(key=lambda match: match.combined_score, reverse=True)
            self._intelligence.apply_originality(
                profile,
                [
                    (match.content_id, match.title, match.combined_score, match.duplicate_kind)
                    for match in matches
                ],
            )
            if profile.duplicate_kind is not DuplicateKind.NONE:
                flags[profile.duplicate_kind.value] += 1
        return dict(flags)
