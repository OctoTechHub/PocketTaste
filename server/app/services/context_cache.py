"""In-memory serving cache for the online ranking path.

Recommendation requests need the whole catalog, its profiles, its features and the
item-item co-occurrence matrix. Reading all of that from Mongo per request would be
absurd. The batch tier (the agent pipeline) writes; this cache serves, and is
invalidated whenever the pipeline finishes or the TTL expires.
"""

from __future__ import annotations

import asyncio

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.logging import get_logger
from app.data.repositories import (
    ActivityRepository,
    ContentFeaturesRepository,
    ContentProfileRepository,
    ContentRepository,
    UserProfileRepository,
)
from app.domain.enums import POSITIVE_EVENTS
from app.domain.provenance import resolve_provenance
from app.services.feature_builder import build_co_occurrence, build_transitions
from app.services.ranking import RankingContext, build_suppression_set

logger = get_logger(__name__)

DEFAULT_TTL_SECONDS = 300.0


class RankingContextCache:
    def __init__(
        self,
        settings: Settings,
        content_repo: ContentRepository,
        profile_repo: ContentProfileRepository,
        features_repo: ContentFeaturesRepository,
        activity_repo: ActivityRepository,
        users_repo: UserProfileRepository,
        *,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._settings = settings
        self._content_repo = content_repo
        self._profile_repo = profile_repo
        self._features_repo = features_repo
        self._activity_repo = activity_repo
        self._users_repo = users_repo
        self._ttl = ttl_seconds
        self._context: RankingContext | None = None
        self._loaded_at: float = 0.0
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._context = None
        self._loaded_at = 0.0

    @property
    def loaded(self) -> bool:
        return self._context is not None

    async def get(self, *, force: bool = False) -> RankingContext:
        age = utcnow().timestamp() - self._loaded_at
        if self._context is not None and not force and age < self._ttl:
            return self._context
        async with self._lock:
            # Re-check: another coroutine may have refreshed while we waited.
            age = utcnow().timestamp() - self._loaded_at
            if self._context is not None and not force and age < self._ttl:
                return self._context
            self._context = await self._load()
            self._loaded_at = utcnow().timestamp()
            return self._context

    async def _load(self) -> RankingContext:
        catalog_items, profiles, features = await asyncio.gather(
            self._content_repo.list_catalog(limit=10_000, with_transcript=False),
            self._profile_repo.all_by_id(),
            self._features_repo.all_by_id(),
        )
        baskets = await self._activity_repo.co_occurrence_pairs(
            [event.value for event in POSITIVE_EVENTS]
        )
        co_occurrence = build_co_occurrence([basket["items"] for basket in baskets])
        # Order-aware companion to co-occurrence, built from each listener's
        # chronological positive history.
        users = await self._users_repo.list_all()
        transitions = build_transitions(
            [profile.recent_sequence for profile in users if len(profile.recent_sequence) > 1]
        )

        total_plays = sum(row.plays for row in features.values())
        events_total = await self._activity_repo.count()
        events_synthetic = await self._activity_repo.count({"is_synthetic": True})
        provenance = resolve_provenance(
            catalog_total=len(catalog_items),
            catalog_synthetic=sum(item.is_synthetic for item in catalog_items),
            events_total=events_total,
            events_synthetic=events_synthetic,
        )

        catalog = {item.content_id: item for item in catalog_items}
        suppressed = build_suppression_set(catalog, profiles)

        logger.info(
            "Ranking context loaded: %d items, %d profiles, %d feature rows, "
            "%d co-occurrence nodes, %d suppressed re-uploads",
            len(catalog_items),
            len(profiles),
            len(features),
            len(co_occurrence),
            len(suppressed),
        )
        return RankingContext(
            catalog=catalog,
            profiles=profiles,
            features=features,
            co_occurrence=co_occurrence,
            transitions=transitions,
            total_plays=total_plays,
            provenance=provenance,
            suppressed=suppressed,
        )
