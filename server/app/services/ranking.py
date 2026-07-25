"""Hybrid ranker.

Three stages, deliberately transparent — every score decomposes into named
signals multiplied by published weights.

  1. Candidate generation  — embedding neighbours of the taste vector
                             UNION item-item co-occurrence neighbours
                             UNION an exploration slice for cold-start coverage.
  2. Scoring               — linear blend of 7 behavioural/content signals.
  3. Re-selection          — Maximal Marginal Relevance, so the returned list is
                             not seven variants of the same story.

No model is trained here. That is a choice: with a hackathon-sized log a trained
ranker would overfit, and an unexplainable score is useless to a creator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.core.clock import as_utc, days_between, utcnow
from app.core.config import Settings
from app.domain.enums import DuplicateKind, Provenance
from app.domain.models import (
    ContentFeatures,
    ContentItem,
    ContentProfile,
    RecommendationResult,
    RecommendationSignals,
    RecommendedItem,
    UserProfile,
)
from app.services.vectors import cosine, cosine_matrix


@dataclass(slots=True)
class RankingContext:
    """Everything the ranker needs, resolved once per request."""

    catalog: dict[str, ContentItem]
    profiles: dict[str, ContentProfile]
    features: dict[str, ContentFeatures]
    co_occurrence: dict[str, dict[str, float]]
    #: First-order 'after A comes B' probabilities. Order-aware, unlike co-occurrence.
    transitions: dict[str, dict[str, float]] = field(default_factory=dict)
    #: Coarse tier of the backoff chain: genre/language -> genre/language.
    segment_transitions: dict[str, dict[str, float]] = field(default_factory=dict)
    total_plays: int = 0
    provenance: Provenance = Provenance.REAL
    #: Re-uploads suppressed from recommendations. See `build_suppression_set`.
    suppressed: set[str] = field(default_factory=set)


def build_suppression_set(
    catalog: dict[str, ContentItem], profiles: dict[str, ContentProfile]
) -> set[str]:
    """Content ids to keep out of recommendations because they are re-uploads.

    Detecting duplicates is pointless if the ranker still promotes them: a listener
    who finished "Ashen Throne" should not be offered "Ashen Throne Season 3", and
    the re-uploader should not harvest impressions the original creator earned.

    Rule: for an item flagged as an exact duplicate or a series variant, suppress it
    when a confirmed near-identical neighbour was published earlier. The earliest
    publication in a duplicate family survives — the original is never suppressed
    just because someone copied it.
    """
    suppressed: set[str] = set()
    for content_id, profile in profiles.items():
        if profile.duplicate_kind not in (DuplicateKind.EXACT_DUPLICATE, DuplicateKind.SERIES_VARIANT):
            continue
        item = catalog.get(content_id)
        if item is None:
            continue
        for neighbour in profile.nearest_neighbours:
            other = catalog.get(neighbour.get("content_id", ""))
            if other is None or neighbour.get("score", 0.0) < _DUPLICATE_SUPPRESSION_SCORE:
                continue
            if as_utc(other.published_at) < as_utc(item.published_at):
                suppressed.add(content_id)
                break
    return suppressed


#: A neighbour must be at least this similar before it can suppress a later upload.
_DUPLICATE_SUPPRESSION_SCORE = 0.85

#: Below this cosine, "similar to what usually comes next" is not a real claim.
_SEQUENCE_SIMILARITY_FLOOR = 0.55


class RankingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # --- entry point --------------------------------------------------------

    def recommend(
        self,
        user: UserProfile,
        context: RankingContext,
        *,
        limit: int = 10,
        language: str | None = None,
        exclude: set[str] | None = None,
        include_seen: bool = False,
        diversity: float | None = None,
        include_duplicates: bool = False,
    ) -> RecommendationResult:
        exclude = set(exclude or set())
        if not include_seen:
            exclude |= set(user.interacted_content_ids)
        suppressed = set() if include_duplicates else context.suppressed
        exclude |= suppressed

        eligible = [
            item
            for item in context.catalog.values()
            if item.content_id not in exclude and (language is None or item.language == language)
        ]
        if not eligible:
            return RecommendationResult(
                user_id=user.user_id,
                items=[],
                strategy="hybrid",
                cold_start=user.is_cold_start,
                suppressed_duplicates=len(suppressed),
                weights=self._settings.ranking_weights.as_dict(),
                mmr_lambda=diversity if diversity is not None else self._settings.mmr_lambda,
                provenance=context.provenance,
                explanation="No eligible catalog items remain after filtering.",
            )

        candidates = self._generate_candidates(user, context, eligible)
        scored = [self._score(user, item, context) for item in candidates]
        scored.sort(key=lambda pair: pair[1], reverse=True)

        selected = self._mmr_select(
            scored,
            context,
            limit=limit,
            lambda_=diversity if diversity is not None else self._settings.mmr_lambda,
        )

        return RecommendationResult(
            user_id=user.user_id,
            items=selected,
            strategy="hybrid_mmr_cold_start" if user.is_cold_start else "hybrid_mmr",
            cold_start=user.is_cold_start,
            candidate_pool_size=len(candidates),
            suppressed_duplicates=len(suppressed),
            weights=self._settings.ranking_weights.as_dict(),
            mmr_lambda=diversity if diversity is not None else self._settings.mmr_lambda,
            provenance=context.provenance,
            explanation=self._strategy_note(user),
            generated_at=utcnow(),
        )

    # --- stage 1: candidate generation --------------------------------------

    def _generate_candidates(
        self, user: UserProfile, context: RankingContext, eligible: list[ContentItem]
    ) -> list[ContentItem]:
        pool_size = self._settings.candidate_pool_size
        if len(eligible) <= pool_size:
            return eligible

        by_id = {item.content_id: item for item in eligible}
        chosen: dict[str, ContentItem] = {}

        # (a) embedding neighbours of the taste vector
        if user.taste_vector:
            ids, matrix = self._stack(eligible, context)
            if matrix.size:
                scores = cosine_matrix(user.taste_vector, matrix)
                for index in np.argsort(-scores)[: pool_size // 2]:
                    chosen[ids[index]] = by_id[ids[index]]

        # (b) co-occurrence neighbours of what the user already liked
        neighbour_scores: dict[str, float] = {}
        for seed in user.positive_content_ids:
            for neighbour, score in context.co_occurrence.get(seed, {}).items():
                if neighbour in by_id:
                    neighbour_scores[neighbour] = max(neighbour_scores.get(neighbour, 0.0), score)
        for content_id, _ in sorted(neighbour_scores.items(), key=lambda pair: -pair[1])[: pool_size // 3]:
            chosen[content_id] = by_id[content_id]

        # (c) exploration slice — newest under-served items keep the catalog reachable
        remaining = [item for item in eligible if item.content_id not in chosen]
        remaining.sort(key=lambda item: (context.features.get(item.content_id, _EMPTY).plays, -item.published_at.timestamp()))
        for item in remaining[: max(0, pool_size - len(chosen))]:
            chosen[item.content_id] = item

        return list(chosen.values())

    @staticmethod
    def _stack(items: list[ContentItem], context: RankingContext) -> tuple[list[str], np.ndarray]:
        ids: list[str] = []
        rows: list[list[float]] = []
        for item in items:
            profile = context.profiles.get(item.content_id)
            if profile and profile.embedding:
                ids.append(item.content_id)
                rows.append(profile.embedding)
        if not rows:
            return [], np.empty((0, 0), dtype=np.float32)
        return ids, np.asarray(rows, dtype=np.float32)

    # --- stage 2: scoring ---------------------------------------------------

    def _score(
        self, user: UserProfile, item: ContentItem, context: RankingContext
    ) -> tuple[ContentItem, float, RecommendationSignals, dict[str, float]]:
        profile = context.profiles.get(item.content_id)
        features = context.features.get(item.content_id, _EMPTY)
        weights = self._settings.ranking_weights

        signals = RecommendationSignals(
            affinity=cosine(user.taste_vector, profile.embedding) if profile and user.taste_vector else 0.0,
            co_occurrence=self._co_occurrence_signal(user, item, context),
            sequence=self._sequence_signal(user, item, context),
            retention=features.quality_score,
            genre_affinity=self._genre_language_signal(user, item),
            freshness=self._freshness(item),
            originality=profile.originality_score if profile else 1.0,
            exploration=self._exploration_bonus(features.plays, context.total_plays),
        )

        contributions = {
            "affinity": round(weights.affinity * signals.affinity, 6),
            "co_occurrence": round(weights.co_occurrence * signals.co_occurrence, 6),
            "sequence": round(weights.sequence * signals.sequence, 6),
            "retention": round(weights.retention * signals.retention, 6),
            "genre_affinity": round(weights.genre_affinity * signals.genre_affinity, 6),
            "freshness": round(weights.freshness * signals.freshness, 6),
            "originality": round(weights.originality * signals.originality, 6),
            "exploration": round(weights.exploration * signals.exploration, 6),
        }
        return item, round(sum(contributions.values()), 6), signals, contributions

    def _sequence_signal(
        self, user: UserProfile, item: ContentItem, context: RankingContext
    ) -> float:
        """P(next = item | what this listener just finished), recency-weighted.

        Co-occurrence answers "who else liked both". This answers "what usually comes
        next" — a different question, and the one that matters for serial audio.

        **Three-tier backoff**, because the exact item pair is almost never observed.
        A 100-item catalog has ~10,000 ordered pairs and a handful of listeners
        produce a few dozen, so a naive lookup returns zero essentially always. Worse,
        a listener's own transitions point at items they have already heard, and heard
        items are excluded from recommendations — so with few users the signal is
        structurally dead. Each tier is discounted by how much it is trusted:

          1.0x  exact item transition       A -> B was actually observed
          0.8x  content-similar transition  A -> X observed, and B resembles X
          0.5x  segment transition          crime-detective/hi -> suspense/hi

        Discounting rather than treating them as equal keeps a coarse guess from
        outranking a real observation.
        """
        if not user.recent_sequence:
            return 0.0
        if not context.transitions and not context.segment_transitions:
            return 0.0

        target_profile = context.profiles.get(item.content_id)
        target_segment = f"{item.primary_genre}/{item.language}"
        best = 0.0

        # Walk backwards from the most recent interaction; older steps decay.
        for distance, previous in enumerate(reversed(user.recent_sequence[-5:])):
            decay = 0.6**distance
            outgoing = context.transitions.get(previous, {})

            # Tier 1: this exact pair was observed.
            exact = outgoing.get(item.content_id, 0.0)
            if exact:
                best = max(best, exact * decay)
                continue

            # Tier 2: we know what usually follows `previous`; is this item like it?
            if target_profile and target_profile.embedding:
                for observed_next, probability in outgoing.items():
                    neighbour = context.profiles.get(observed_next)
                    if not neighbour or not neighbour.embedding:
                        continue
                    similarity = cosine(target_profile.embedding, neighbour.embedding)
                    if similarity >= _SEQUENCE_SIMILARITY_FLOOR:
                        best = max(best, probability * similarity * decay * 0.8)

            # Tier 3: fall back to where listeners go at the segment level.
            previous_item = context.catalog.get(previous)
            if previous_item is not None:
                previous_segment = f"{previous_item.primary_genre}/{previous_item.language}"
                segment_probability = context.segment_transitions.get(previous_segment, {}).get(
                    target_segment, 0.0
                )
                if segment_probability:
                    best = max(best, segment_probability * decay * 0.5)

        return round(min(1.0, best), 6)

    @staticmethod
    def _co_occurrence_signal(user: UserProfile, item: ContentItem, context: RankingContext) -> float:
        if not user.positive_content_ids:
            return 0.0
        scores = [
            context.co_occurrence.get(seed, {}).get(item.content_id, 0.0)
            for seed in user.positive_content_ids
        ]
        return round(max(scores, default=0.0), 6)

    @staticmethod
    def _genre_language_signal(user: UserProfile, item: ContentItem) -> float:
        """Blend of learned genre affinity and language match.

        Language is a hard preference in audio: a Hindi-only listener will not
        finish an English story however well it matches semantically.
        """
        genre_score = max(
            (user.genre_affinity.get(genre, 0.0) for genre in item.genres or ["general"]), default=0.0
        )
        # Affinities are softmax-normalised, so rescale against the user's own peak.
        peak = max(user.genre_affinity.values(), default=0.0) or 1.0
        genre_component = min(1.0, genre_score / peak)
        language_component = user.language_affinity.get(item.language, 0.0)
        language_peak = max(user.language_affinity.values(), default=0.0) or 1.0
        return round(0.6 * genre_component + 0.4 * min(1.0, language_component / language_peak), 6)

    def _freshness(self, item: ContentItem) -> float:
        """Exponential decay with a configurable half-life."""
        age_days = days_between(utcnow(), item.published_at)
        return round(math.exp(-math.log(2) * age_days / self._settings.freshness_half_life_days), 6)

    @staticmethod
    def _exploration_bonus(item_plays: int, total_plays: int) -> float:
        """UCB1-style optimism. Under-observed items get lifted so the catalog does
        not collapse onto whatever was popular on day one."""
        if total_plays <= 0:
            return 1.0
        bonus = math.sqrt(2.0 * math.log(total_plays + 1) / (item_plays + 1))
        ceiling = math.sqrt(2.0 * math.log(total_plays + 1))
        return round(min(1.0, bonus / ceiling if ceiling else 1.0), 6)

    # --- stage 3: MMR re-selection ------------------------------------------

    def _mmr_select(
        self,
        scored: list[tuple[ContentItem, float, RecommendationSignals, dict[str, float]]],
        context: RankingContext,
        *,
        limit: int,
        lambda_: float,
    ) -> list[RecommendedItem]:
        """Maximal Marginal Relevance: trade relevance against redundancy.

            mmr = λ * relevance - (1 - λ) * max_similarity_to_already_selected
        """
        pool = scored[: max(limit * 5, limit)]
        selected: list[tuple[ContentItem, float, RecommendationSignals, dict[str, float], float]] = []
        remaining = list(pool)

        while remaining and len(selected) < limit:
            best_index, best_value = 0, -math.inf
            for index, (item, relevance, _, _) in enumerate(remaining):
                penalty = max(
                    (
                        self._pair_similarity(item, chosen[0], context)
                        for chosen in selected
                    ),
                    default=0.0,
                )
                value = lambda_ * relevance - (1.0 - lambda_) * penalty
                if value > best_value:
                    best_index, best_value = index, value
            item, relevance, signals, contributions = remaining.pop(best_index)
            selected.append((item, relevance, signals, contributions, round(best_value, 6)))

        return [
            RecommendedItem(
                content_id=item.content_id,
                title=item.title,
                language=item.language,
                genres=item.genres,
                relevance_score=relevance,
                final_score=final,
                rank=rank,
                signals=signals,
                contributions=contributions,
                reason=self._reason(signals, contributions),
            )
            for rank, (item, relevance, signals, contributions, final) in enumerate(selected, start=1)
        ]

    @staticmethod
    def _pair_similarity(left: ContentItem, right: ContentItem, context: RankingContext) -> float:
        left_profile = context.profiles.get(left.content_id)
        right_profile = context.profiles.get(right.content_id)
        if left_profile and right_profile and left_profile.embedding and right_profile.embedding:
            return cosine(left_profile.embedding, right_profile.embedding)
        # Fall back to genre overlap when embeddings are unavailable.
        shared = set(left.genres) & set(right.genres)
        return 1.0 if shared and left.language == right.language else 0.0

    @staticmethod
    def _reason(signals: RecommendationSignals, contributions: dict[str, float]) -> str:
        """Deterministic, per-item 'why'. The LLM layer only rephrases this — it never
        invents a different reason."""
        top = sorted(contributions.items(), key=lambda pair: pair[1], reverse=True)[:2]
        phrases = {
            "affinity": f"matches your listening taste ({signals.affinity:.2f} similarity)",
            "co_occurrence": f"listeners with your history also finished it ({signals.co_occurrence:.2f})",
            "sequence": f"commonly the next listen after what you just finished ({signals.sequence:.2f})",
            "retention": f"strong retention across listeners ({signals.retention:.2f})",
            "genre_affinity": f"in a genre and language you return to ({signals.genre_affinity:.2f})",
            "freshness": f"recently published ({signals.freshness:.2f} freshness)",
            "originality": f"distinct from existing catalog stories ({signals.originality:.2f} originality)",
            "exploration": f"under-served title surfaced for coverage ({signals.exploration:.2f})",
        }
        parts = [phrases[name] for name, value in top if value > 0]
        return "Recommended because it " + " and ".join(parts) + "." if parts else (
            "Recommended as a baseline discovery pick; no strong personal signal yet."
        )

    @staticmethod
    def _strategy_note(user: UserProfile) -> str:
        if user.is_cold_start:
            return (
                "Cold-start path: fewer than two positive interactions are on record, so ranking "
                "leans on content quality, freshness and exploration rather than personal history."
            )
        return (
            "Hybrid ranking blends taste-vector affinity, item-item co-occurrence, observed retention, "
            "genre/language affinity, freshness, originality and an exploration bonus, then applies MMR "
            "for diversity. This layer is independent of any platform-side recommender."
        )


_EMPTY = ContentFeatures(content_id="__empty__")
