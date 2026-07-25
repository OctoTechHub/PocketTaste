"""Agent 1 of 3 — Ingestion.

Turns the raw event log into behavioural features. Entirely deterministic: no LLM,
no sampling, no randomness. Given the same log it produces the same numbers, which
is the only reason the creator-facing metrics can be defended.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from app.agents.base import Agent, AgentOptions, AgentOutcome
from app.core.config import Settings
from app.core.logging import get_logger
from app.data.repositories import (
    ActivityRepository,
    ContentFeaturesRepository,
    ContentProfileRepository,
    ContentRepository,
    UserProfileRepository,
)
from app.domain.enums import AgentName, EventType, Provenance
from app.domain.models import ActivityEvent
from app.domain.provenance import resolve_provenance
from app.services.feature_builder import build_content_features, build_user_profile

logger = get_logger(__name__)


class IngestionAgent(Agent):
    name = AgentName.INGESTION

    def __init__(
        self,
        settings: Settings,
        content_repo: ContentRepository,
        activity_repo: ActivityRepository,
        features_repo: ContentFeaturesRepository,
        users_repo: UserProfileRepository,
        profiles_repo: ContentProfileRepository,
    ) -> None:
        self._settings = settings
        self._content_repo = content_repo
        self._activity_repo = activity_repo
        self._features_repo = features_repo
        self._users_repo = users_repo
        self._profiles_repo = profiles_repo

    async def execute(self, options: AgentOptions) -> AgentOutcome:
        catalog = await self._content_repo.iter_all(with_transcript=False)
        if not catalog:
            return AgentOutcome(stats={"reason": "empty_catalog"})

        events = await self._activity_repo.stream_all()
        if not events:
            return AgentOutcome(processed=0, stats={"reason": "no_activity_logged"})

        catalog_by_id = {item.content_id: item for item in catalog}
        profiles = await self._profiles_repo.all_by_id()

        by_content: dict[str, list[ActivityEvent]] = defaultdict(list)
        by_user: dict[str, list[ActivityEvent]] = defaultdict(list)
        for event in events:
            by_user[event.user_id].append(event)
            if event.content_id:
                by_content[event.content_id].append(event)

        features = [
            build_content_features(
                item,
                by_content.get(item.content_id, []),
                min_confident_sample_size=self._settings.min_confident_sample_size,
            )
            for item in catalog
        ]
        features_written = await self._features_repo.upsert_many(features)

        catalog_median_duration = median(item.duration_seconds for item in catalog)
        user_profiles = [
            build_user_profile(
                user_id,
                user_events,
                catalog_by_id,
                profiles,
                catalog_median_duration=catalog_median_duration,
            )
            for user_id, user_events in by_user.items()
        ]
        users_written = await self._users_repo.upsert_many(user_profiles)

        synthetic_events = sum(event.is_synthetic for event in events)
        cold_start = sum(profile.is_cold_start for profile in user_profiles)
        with_taste_vector = sum(bool(profile.taste_vector) for profile in user_profiles)

        return AgentOutcome(
            processed=len(events),
            written=features_written + users_written,
            skipped=len(events) - sum(len(rows) for rows in by_content.values()),
            stats={
                "content_features": len(features),
                "user_profiles": len(user_profiles),
                "cold_start_users": cold_start,
                "users_with_taste_vector": with_taste_vector,
                "events_by_type": self._event_counts(events),
                "search_events": sum(event.event_type is EventType.SEARCH for event in events),
                "zero_result_searches": sum(
                    event.event_type is EventType.SEARCH and event.result_count == 0 for event in events
                ),
                "provenance": resolve_provenance(
                    catalog_total=len(catalog),
                    catalog_synthetic=sum(item.is_synthetic for item in catalog),
                    events_total=len(events),
                    events_synthetic=synthetic_events,
                ).value,
                "synthetic_event_share": round(synthetic_events / len(events), 4),
            },
        )

    @staticmethod
    def _event_counts(events: list[ActivityEvent]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for event in events:
            counts[event.event_type.value] += 1
        return dict(sorted(counts.items()))

