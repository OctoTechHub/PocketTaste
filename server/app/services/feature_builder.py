"""Raw event logs -> behavioural features.

Everything in this module is a pure function of (events, catalog). No IO, no LLM,
no randomness — the same log always yields the same features, which is what makes
the creator metrics defensible.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median

from app.core.clock import utcnow
from app.domain.enums import (
    EVENT_WEIGHTS,
    POSITIVE_EVENTS,
    Confidence,
    EventType,
    Pacing,
    Provenance,
)
from app.domain.provenance import resolve_provenance
from app.domain.models import (
    ActivityEvent,
    ChapterInterest,
    ContentFeatures,
    ContentItem,
    ContentProfile,
    RetentionPoint,
    UserProfile,
)
from app.services.vectors import softmax_normalise, weighted_mean

DECILES = 10


def _confidence(sample_size: int, threshold: int) -> Confidence:
    if sample_size >= threshold:
        return Confidence.HIGH
    if sample_size >= max(2, threshold // 3):
        return Confidence.MEDIUM
    return Confidence.LOW


def _provenance(item: ContentItem, events: list[ActivityEvent]) -> Provenance:
    return resolve_provenance(
        catalog_total=1,
        catalog_synthetic=int(item.is_synthetic),
        events_total=len(events),
        events_synthetic=sum(event.is_synthetic for event in events),
    )


def _logistic(value: float, steepness: float = 2.0) -> float:
    return 1.0 / (1.0 + math.exp(-steepness * value))


def _safe_ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


# ---------------------------------------------------------------------------
# Content-level features
# ---------------------------------------------------------------------------


def build_content_features(
    item: ContentItem,
    events: list[ActivityEvent],
    *,
    min_confident_sample_size: int = 30,
) -> ContentFeatures:
    """Behavioural fingerprint of one catalog item."""
    playback = [event for event in events if event.event_type is not EventType.SEARCH]
    listeners = {event.user_id for event in playback}
    sessions = {event.session_id for event in playback}

    counts: dict[EventType, int] = defaultdict(int)
    for event in playback:
        counts[event.event_type] += 1

    plays = counts[EventType.PLAY]
    denominator = max(plays, len(listeners), 1)  # never divide by zero, never inflate

    abandons = [event.position_seconds for event in playback if event.event_type is EventType.DROP_OFF]
    median_abandon = int(median(abandons)) if abandons else None

    sessions_per_listener: dict[str, set[str]] = defaultdict(set)
    for event in playback:
        sessions_per_listener[event.user_id].add(event.session_id)
    returning = sum(1 for user_sessions in sessions_per_listener.values() if len(user_sessions) > 1)

    session_lengths = [event.session_seconds for event in playback if event.session_seconds > 0]

    completion_rate = _safe_ratio(counts[EventType.COMPLETE], denominator)
    skip_rate = _safe_ratio(counts[EventType.SKIP], denominator)
    replay_rate = _safe_ratio(counts[EventType.REPLAY], denominator)
    drop_off_rate = _safe_ratio(counts[EventType.DROP_OFF], denominator)
    re_engagement_rate = _safe_ratio(returning, len(listeners))

    quality = (
        0.45 * completion_rate
        + 0.20 * (1.0 - min(drop_off_rate, 1.0))
        + 0.20 * re_engagement_rate
        + 0.15 * min(replay_rate, 1.0)
    )

    return ContentFeatures(
        content_id=item.content_id,
        plays=plays,
        unique_listeners=len(listeners),
        sessions=len(sessions),
        completions=counts[EventType.COMPLETE],
        completion_rate=round(min(completion_rate, 1.0), 4),
        skip_rate=round(min(skip_rate, 1.0), 4),
        replay_rate=round(replay_rate, 4),
        drop_off_rate=round(min(drop_off_rate, 1.0), 4),
        median_abandon_seconds=median_abandon,
        abandon_point_ratio=(
            round(median_abandon / item.duration_seconds, 4) if median_abandon is not None else None
        ),
        avg_session_seconds=round(sum(session_lengths) / len(session_lengths), 2) if session_lengths else 0.0,
        re_engagement_rate=round(re_engagement_rate, 4),
        retention_curve=_retention_curve(item, playback),
        chapter_interest=_chapter_interest(item, playback),
        quality_score=round(max(0.0, min(1.0, quality)), 4),
        sample_size=len(listeners),
        confidence=_confidence(len(listeners), min_confident_sample_size),
        provenance=_provenance(item, playback),
        computed_at=utcnow(),
    )


def _retention_curve(item: ContentItem, events: list[ActivityEvent]) -> list[RetentionPoint]:
    """Share of listeners still present at each 10% mark of the runtime."""
    furthest: dict[str, int] = defaultdict(int)
    for event in events:
        if event.event_type is EventType.COMPLETE:
            furthest[event.user_id] = item.duration_seconds
        else:
            furthest[event.user_id] = max(furthest[event.user_id], event.position_seconds)
    if not furthest:
        return []
    total = len(furthest)
    curve: list[RetentionPoint] = []
    for decile in range(1, DECILES + 1):
        mark = int(item.duration_seconds * decile / DECILES)
        retained = sum(1 for position in furthest.values() if position >= mark)
        curve.append(
            RetentionPoint(
                decile=decile, position_seconds=mark, retained_ratio=round(retained / total, 4)
            )
        )
    return curve


def _chapter_interest(item: ContentItem, events: list[ActivityEvent]) -> list[ChapterInterest]:
    """Chapter-level signal: which parts get re-listened, which parts lose people.

    This is the granularity session-level collaborative filtering cannot see.
    """
    if not item.chapters:
        return []

    def resolve_chapter(event: ActivityEvent) -> int | None:
        if event.chapter_index is not None:
            return event.chapter_index
        for chapter in item.chapters:
            if chapter.start_seconds <= event.position_seconds < max(chapter.end_seconds, chapter.start_seconds + 1):
                return chapter.index
        return None

    buckets: dict[int, dict] = {
        chapter.index: {"replays": 0, "drop_offs": 0, "jumps_in": 0, "skips": 0, "listeners": set()}
        for chapter in item.chapters
    }
    for event in events:
        index = resolve_chapter(event)
        if index is None or index not in buckets:
            continue
        bucket = buckets[index]
        bucket["listeners"].add(event.user_id)
        if event.event_type is EventType.REPLAY:
            bucket["replays"] += 1
        elif event.event_type is EventType.DROP_OFF:
            bucket["drop_offs"] += 1
        elif event.event_type is EventType.CHAPTER_JUMP:
            bucket["jumps_in"] += 1
        elif event.event_type is EventType.SKIP:
            bucket["skips"] += 1

    interest: list[ChapterInterest] = []
    for chapter in item.chapters:
        bucket = buckets[chapter.index]
        listeners = max(len(bucket["listeners"]), 1)
        raw = (
            bucket["replays"] + 0.5 * bucket["jumps_in"] - bucket["drop_offs"] - 0.5 * bucket["skips"]
        ) / listeners
        interest.append(
            ChapterInterest(
                chapter_index=chapter.index,
                title=chapter.title,
                replays=bucket["replays"],
                drop_offs=bucket["drop_offs"],
                jumps_in=bucket["jumps_in"],
                skips=bucket["skips"],
                listeners=len(bucket["listeners"]),
                interest_score=round(_logistic(raw), 4),
            )
        )
    return interest


# ---------------------------------------------------------------------------
# User-level features
# ---------------------------------------------------------------------------


def build_user_profile(
    user_id: str,
    events: list[ActivityEvent],
    catalog: dict[str, ContentItem],
    profiles: dict[str, ContentProfile],
    *,
    catalog_median_duration: float,
) -> UserProfile:
    """Taste state for one listener, derived only from their own events."""
    playback = [event for event in events if event.content_id and event.content_id in catalog]

    vectors: list[list[float]] = []
    weights: list[float] = []
    genre_scores: dict[str, float] = defaultdict(float)
    language_scores: dict[str, float] = defaultdict(float)
    interacted: list[str] = []
    positives: list[str] = []
    abandon_ratios: list[float] = []
    completed_durations: list[int] = []
    plays = completes = 0

    for event in playback:
        item = catalog[event.content_id]  # type: ignore[index]
        weight = EVENT_WEIGHTS.get(event.event_type, 0.0)

        # An abandon at 5% is a much stronger rejection than one at 85%.
        if event.event_type is EventType.DROP_OFF and item.duration_seconds:
            ratio = min(1.0, event.position_seconds / item.duration_seconds)
            abandon_ratios.append(ratio)
            weight *= 1.0 - 0.7 * ratio

        if event.event_type is EventType.PLAY:
            plays += 1
        if event.event_type is EventType.COMPLETE:
            completes += 1
            completed_durations.append(item.duration_seconds)

        if event.content_id not in interacted:
            interacted.append(event.content_id)  # type: ignore[arg-type]
        if event.event_type in POSITIVE_EVENTS and event.content_id not in positives:
            positives.append(event.content_id)  # type: ignore[arg-type]

        if weight:
            for genre in item.genres or ["general"]:
                genre_scores[genre] += weight
            language_scores[item.language] += weight
            profile = profiles.get(event.content_id or "")
            if profile and profile.embedding:
                vectors.append(profile.embedding)
                weights.append(weight)

    avg_abandon = round(sum(abandon_ratios) / len(abandon_ratios), 4) if abandon_ratios else None
    sessions = {event.session_id for event in playback}

    return UserProfile(
        user_id=user_id,
        taste_vector=weighted_mean(vectors, weights),
        genre_affinity=softmax_normalise(dict(genre_scores)),
        language_affinity=softmax_normalise(dict(language_scores)),
        pacing_preference=_infer_pacing(completed_durations, avg_abandon, catalog_median_duration),
        completion_propensity=round(completes / plays, 4) if plays else 0.0,
        avg_abandon_ratio=avg_abandon,
        re_engagement_score=round(min(1.0, len(sessions) / max(len(interacted), 1)), 4),
        interacted_content_ids=interacted,
        positive_content_ids=positives,
        events_observed=len(playback),
        sessions_observed=len(sessions),
        is_cold_start=len(positives) < 2,
        last_active_at=max((event.occurred_at for event in playback), default=None),
        computed_at=utcnow(),
    )


def _infer_pacing(
    completed_durations: list[int], avg_abandon_ratio: float | None, catalog_median: float
) -> Pacing:
    """Listeners who finish long-form content are 'slow'; early bailers are 'fast'."""
    if avg_abandon_ratio is not None and avg_abandon_ratio < 0.25 and not completed_durations:
        return Pacing.FAST
    if not completed_durations or catalog_median <= 0:
        return Pacing.MEDIUM
    average = sum(completed_durations) / len(completed_durations)
    if average > catalog_median * 1.2:
        return Pacing.SLOW
    if average < catalog_median * 0.8:
        return Pacing.FAST
    return Pacing.MEDIUM


# ---------------------------------------------------------------------------
# Item-item co-occurrence (the collaborative half of the hybrid)
# ---------------------------------------------------------------------------


def build_co_occurrence(baskets: list[list[str]]) -> dict[str, dict[str, float]]:
    """Cosine-normalised item-item co-occurrence from per-user positive baskets.

    cooc(a, b) = |users(a) & users(b)| / sqrt(|users(a)| * |users(b)|)

    Normalising by item popularity stops blockbusters from dominating every
    neighbour list — the classic failure mode of raw co-counts.
    """
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    item_counts: dict[str, int] = defaultdict(int)

    for basket in baskets:
        unique = sorted(set(basket))
        for item in unique:
            item_counts[item] += 1
        for i, left in enumerate(unique):
            for right in unique[i + 1 :]:
                pair_counts[(left, right)] += 1

    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    for (left, right), shared in pair_counts.items():
        denominator = math.sqrt(item_counts[left] * item_counts[right])
        if denominator <= 0:
            continue
        score = round(shared / denominator, 6)
        matrix[left][right] = score
        matrix[right][left] = score
    return dict(matrix)
