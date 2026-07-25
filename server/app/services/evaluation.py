"""Offline evaluation of the ranker.

Method: **global temporal holdout**, not random leave-one-out.

Events are ordered by time and split at the 80th percentile. Everything before the
split is the only thing the ranker may see — user profiles, content features and
the co-occurrence matrix are all rebuilt from the training slice alone. Positive
interactions after the split are the ground truth.

This matters. Random leave-one-out leaks the future into the features: a content
item's completion rate computed over the whole log already encodes the very
interaction you are trying to predict, and the resulting Recall@K is inflated. The
temporal split reproduces the real serving condition — predict tomorrow from today.

Two baselines are reported alongside the hybrid ranker, because a Recall@K with
nothing to compare it to means nothing:
  * popularity — rank by training-set play count (a strong baseline in practice)
  * random     — seeded uniform sample (the floor)

Content embeddings are reused across both slices. They are derived from the text of
the story, not from behaviour, so they carry no future information.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median

from app.core.clock import utcnow
from app.core.config import Settings
from app.domain.enums import POSITIVE_EVENTS, Provenance
from app.domain.models import ActivityEvent, ContentItem, ContentProfile, UserProfile
from app.domain.provenance import resolve_provenance
from app.services.feature_builder import (
    build_co_occurrence,
    build_content_features,
    build_user_profile,
)
from app.services.ranking import RankingContext, RankingService, build_suppression_set

RANDOM_SEED = 20260725


@dataclass(slots=True)
class MetricSet:
    strategy: str
    users_evaluated: int = 0
    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    ndcg_at_k: float = 0.0
    mrr: float = 0.0
    hit_rate: float = 0.0
    catalog_coverage: float = 0.0
    novelty: float = 0.0
    intra_list_diversity: float = 0.0

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "users_evaluated": self.users_evaluated,
            "recall_at_k": round(self.recall_at_k, 4),
            "precision_at_k": round(self.precision_at_k, 4),
            "ndcg_at_k": round(self.ndcg_at_k, 4),
            "mrr": round(self.mrr, 4),
            "hit_rate": round(self.hit_rate, 4),
            "catalog_coverage": round(self.catalog_coverage, 4),
            "novelty": round(self.novelty, 4),
            "intra_list_diversity": round(self.intra_list_diversity, 4),
        }


@dataclass(slots=True)
class EvaluationReport:
    k: int
    train_events: int
    test_events: int
    split_at: str
    users_evaluated: int
    catalog_size: int
    provenance: Provenance
    results: list[MetricSet] = field(default_factory=list)
    lift_vs_popularity: dict = field(default_factory=dict)
    method: str = ""
    caveats: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "k": self.k,
            "method": self.method,
            "split_at": self.split_at,
            "train_events": self.train_events,
            "test_events": self.test_events,
            "users_evaluated": self.users_evaluated,
            "catalog_size": self.catalog_size,
            "provenance": self.provenance.value,
            "results": [result.as_dict() for result in self.results],
            "lift_vs_popularity": self.lift_vs_popularity,
            "caveats": self.caveats,
            "generated_at": utcnow().isoformat(),
        }


class EvaluationService:
    def __init__(self, settings: Settings, ranking: RankingService) -> None:
        self._settings = settings
        self._ranking = ranking

    def evaluate(
        self,
        catalog: list[ContentItem],
        events: list[ActivityEvent],
        profiles: dict[str, ContentProfile],
        *,
        k: int = 10,
        max_users: int = 200,
        min_interactions: int = 3,
        train_ratio: float = 0.8,
    ) -> EvaluationReport:
        catalog_by_id = {item.content_id: item for item in catalog}
        ordered = sorted(
            (event for event in events if event.content_id in catalog_by_id),
            key=lambda event: event.occurred_at,
        )
        if len(ordered) < 20 or len(catalog) < k:
            return self._empty_report(k, len(ordered), len(catalog))

        split_index = int(len(ordered) * train_ratio)
        train, test = ordered[:split_index], ordered[split_index:]
        if not test:
            return self._empty_report(k, len(ordered), len(catalog))

        context = self._build_context(catalog, train, profiles)
        train_profiles = self._build_user_profiles(catalog_by_id, train, profiles)
        ground_truth = self._ground_truth(test)

        eligible = [
            user_id
            for user_id, truth in ground_truth.items()
            if user_id in train_profiles
            and len(train_profiles[user_id].interacted_content_ids) >= min_interactions
            and truth - set(train_profiles[user_id].interacted_content_ids)
        ][:max_users]

        if not eligible:
            return self._empty_report(k, len(ordered), len(catalog), reason="no_eligible_users")

        popularity = self._popularity(train)
        rng = random.Random(RANDOM_SEED)
        all_ids = sorted(catalog_by_id)

        hybrid = self._score_strategy(
            "hybrid_mmr",
            eligible,
            ground_truth,
            train_profiles,
            catalog_by_id,
            profiles,
            popularity,
            k=k,
            ranker=lambda user: [
                item.content_id
                for item in self._ranking.recommend(user, context, limit=k).items
            ],
        )
        popular = self._score_strategy(
            "popularity_baseline",
            eligible,
            ground_truth,
            train_profiles,
            catalog_by_id,
            profiles,
            popularity,
            k=k,
            ranker=lambda user: [
                content_id
                for content_id, _ in sorted(popularity.items(), key=lambda pair: -pair[1])
                if content_id not in set(user.interacted_content_ids)
            ][:k],
        )
        chance = self._score_strategy(
            "random_baseline",
            eligible,
            ground_truth,
            train_profiles,
            catalog_by_id,
            profiles,
            popularity,
            k=k,
            ranker=lambda user: rng.sample(
                [cid for cid in all_ids if cid not in set(user.interacted_content_ids)],
                min(k, max(0, len(all_ids) - len(set(user.interacted_content_ids)))),
            ),
        )

        return EvaluationReport(
            k=k,
            train_events=len(train),
            test_events=len(test),
            split_at=train[-1].occurred_at.isoformat(),
            users_evaluated=len(eligible),
            catalog_size=len(catalog),
            provenance=self._provenance(ordered),
            results=[hybrid, popular, chance],
            lift_vs_popularity=self._lift(hybrid, popular),
            method=(
                f"Global temporal holdout at {train_ratio:.0%} of the event stream. User profiles, "
                "content features and item-item co-occurrence are rebuilt from the training slice "
                "only; ground truth is post-split positive interactions."
            ),
            caveats=self._caveats(eligible, ordered, catalog),
        )

    # --- context construction ----------------------------------------------

    def _build_context(
        self,
        catalog: list[ContentItem],
        train: list[ActivityEvent],
        profiles: dict[str, ContentProfile],
    ) -> RankingContext:
        by_content: dict[str, list[ActivityEvent]] = defaultdict(list)
        for event in train:
            if event.content_id:
                by_content[event.content_id].append(event)

        features = {
            item.content_id: build_content_features(
                item,
                by_content.get(item.content_id, []),
                min_confident_sample_size=self._settings.min_confident_sample_size,
            )
            for item in catalog
        }
        baskets: dict[str, set[str]] = defaultdict(set)
        for event in train:
            if event.event_type in POSITIVE_EVENTS and event.content_id:
                baskets[event.user_id].add(event.content_id)

        catalog_by_id = {item.content_id: item for item in catalog}
        return RankingContext(
            catalog=catalog_by_id,
            profiles=profiles,
            features=features,
            co_occurrence=build_co_occurrence([sorted(items) for items in baskets.values()]),
            total_plays=sum(row.plays for row in features.values()),
            provenance=self._provenance(train),
            suppressed=build_suppression_set(catalog_by_id, profiles),
        )

    def _build_user_profiles(
        self,
        catalog_by_id: dict[str, ContentItem],
        train: list[ActivityEvent],
        profiles: dict[str, ContentProfile],
    ) -> dict[str, UserProfile]:
        by_user: dict[str, list[ActivityEvent]] = defaultdict(list)
        for event in train:
            by_user[event.user_id].append(event)
        catalog_median = median(item.duration_seconds for item in catalog_by_id.values())
        return {
            user_id: build_user_profile(
                user_id, user_events, catalog_by_id, profiles, catalog_median_duration=catalog_median
            )
            for user_id, user_events in by_user.items()
        }

    @staticmethod
    def _ground_truth(test: list[ActivityEvent]) -> dict[str, set[str]]:
        truth: dict[str, set[str]] = defaultdict(set)
        for event in test:
            if event.event_type in POSITIVE_EVENTS and event.content_id:
                truth[event.user_id].add(event.content_id)
        return dict(truth)

    @staticmethod
    def _popularity(train: list[ActivityEvent]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for event in train:
            if event.content_id:
                counts[event.content_id] += 1
        return dict(counts)

    # --- metric computation -------------------------------------------------

    def _score_strategy(
        self,
        strategy: str,
        users: list[str],
        ground_truth: dict[str, set[str]],
        train_profiles: dict[str, UserProfile],
        catalog_by_id: dict[str, ContentItem],
        profiles: dict[str, ContentProfile],
        popularity: dict[str, int],
        *,
        k: int,
        ranker,
    ) -> MetricSet:
        recalls, precisions, ndcgs, reciprocal_ranks, hits = [], [], [], [], []
        recommended_items: set[str] = set()
        novelties, diversities = [], []
        total_plays = sum(popularity.values()) or 1

        for user_id in users:
            user = train_profiles[user_id]
            seen = set(user.interacted_content_ids)
            truth = ground_truth[user_id] - seen
            if not truth:
                continue
            ranked = [cid for cid in ranker(user) if cid not in seen][:k]
            if not ranked:
                continue
            recommended_items.update(ranked)

            relevant = [1 if cid in truth else 0 for cid in ranked]
            hit_count = sum(relevant)
            recalls.append(hit_count / len(truth))
            precisions.append(hit_count / k)
            hits.append(1.0 if hit_count else 0.0)
            ndcgs.append(self._ndcg(relevant, len(truth), k))
            reciprocal_ranks.append(
                next((1.0 / (index + 1) for index, flag in enumerate(relevant) if flag), 0.0)
            )
            novelties.append(self._novelty(ranked, popularity, total_plays))
            diversities.append(self._diversity(ranked, profiles))

        count = len(recalls)
        return MetricSet(
            strategy=strategy,
            users_evaluated=count,
            recall_at_k=sum(recalls) / count if count else 0.0,
            precision_at_k=sum(precisions) / count if count else 0.0,
            ndcg_at_k=sum(ndcgs) / count if count else 0.0,
            mrr=sum(reciprocal_ranks) / count if count else 0.0,
            hit_rate=sum(hits) / count if count else 0.0,
            catalog_coverage=len(recommended_items) / len(catalog_by_id) if catalog_by_id else 0.0,
            novelty=sum(novelties) / count if count else 0.0,
            intra_list_diversity=sum(diversities) / count if count else 0.0,
        )

    @staticmethod
    def _ndcg(relevance: list[int], truth_size: int, k: int) -> float:
        dcg = sum(flag / math.log2(index + 2) for index, flag in enumerate(relevance))
        ideal = sum(1.0 / math.log2(index + 2) for index in range(min(truth_size, k)))
        return dcg / ideal if ideal else 0.0

    @staticmethod
    def _novelty(ranked: list[str], popularity: dict[str, int], total: int) -> float:
        """Mean self-information: -log2(p(item)). Higher = less obvious picks."""
        if not ranked:
            return 0.0
        scores = [
            -math.log2(max(popularity.get(cid, 0), 1) / total) for cid in ranked
        ]
        return sum(scores) / len(scores)

    @staticmethod
    def _diversity(ranked: list[str], profiles: dict[str, ContentProfile]) -> float:
        """1 - mean pairwise cosine across the returned list."""
        from app.services.vectors import cosine

        vectors = [profiles[cid].embedding for cid in ranked if cid in profiles and profiles[cid].embedding]
        if len(vectors) < 2:
            return 0.0
        pairs = [
            cosine(vectors[i], vectors[j])
            for i in range(len(vectors))
            for j in range(i + 1, len(vectors))
        ]
        return 1.0 - (sum(pairs) / len(pairs))

    @staticmethod
    def _lift(hybrid: MetricSet, baseline: MetricSet) -> dict:
        def ratio(left: float, right: float) -> float | None:
            return round((left - right) / right, 4) if right > 0 else None

        return {
            "recall_at_k": ratio(hybrid.recall_at_k, baseline.recall_at_k),
            "ndcg_at_k": ratio(hybrid.ndcg_at_k, baseline.ndcg_at_k),
            "mrr": ratio(hybrid.mrr, baseline.mrr),
            "catalog_coverage": ratio(hybrid.catalog_coverage, baseline.catalog_coverage),
            "note": "Relative change of the hybrid ranker over the popularity baseline. null = baseline scored zero.",
        }

    def _caveats(
        self, users: list[str], events: list[ActivityEvent], catalog: list[ContentItem]
    ) -> list[str]:
        caveats = [
            "Content embeddings are shared across both slices. They are text-derived, so they "
            "encode no post-split behaviour.",
        ]
        if len(users) < self._settings.min_confident_sample_size:
            caveats.append(
                f"Only {len(users)} users met the evaluation criteria — treat these numbers as "
                "directional, not statistically significant."
            )
        if len(catalog) < 50:
            caveats.append(
                f"Catalog is {len(catalog)} items. Recall@K is optimistic on small catalogs because "
                "the candidate space is small."
            )
        if all(event.is_synthetic for event in events):
            caveats.append(
                "All evaluated events are SYNTHETIC. These metrics validate that the pipeline "
                "computes correctly; they say nothing about real-world accuracy."
            )
        return caveats

    @staticmethod
    def _provenance(events: list[ActivityEvent]) -> Provenance:
        return resolve_provenance(
            catalog_total=0,
            catalog_synthetic=0,
            events_total=len(events),
            events_synthetic=sum(event.is_synthetic for event in events),
        )

    def _empty_report(
        self, k: int, event_count: int, catalog_size: int, reason: str = "insufficient_data"
    ) -> EvaluationReport:
        return EvaluationReport(
            k=k,
            train_events=0,
            test_events=0,
            split_at="",
            users_evaluated=0,
            catalog_size=catalog_size,
            provenance=Provenance.REAL,
            results=[],
            method="not run",
            caveats=[
                f"Evaluation skipped ({reason}): {event_count} usable events across "
                f"{catalog_size} catalog items is below the minimum needed for a meaningful split."
            ],
        )
