"""Stage 0: turn a listener's raw behavior stream into a taste profile.

The core object is the *taste vector* — a weighted average of the embeddings of
series they engaged with. Finishing a series and unlocking coins push strongly
toward that content; dropping pushes away. Genre/tone/language/pacing affinities
are accumulated the same way and normalized to 0..1.
"""
from __future__ import annotations

from app.domain.models import BehaviorEvent, Series, TasteProfile

EVENT_WEIGHT: dict[str, float] = {
    "play": 0.2,
    "complete_episode": 0.5,
    "complete_series": 3.0,
    "coin_unlock": 1.5,
    "skip_intro": -0.2,
    "drop": -1.5,
    "rate": 0.0,  # handled via `value`
}


def build_taste_profile(
    user_id: str, events: list[BehaviorEvent], catalog: list[Series]
) -> TasteProfile:
    by_id = {s.id: s for s in catalog}
    series_weight: dict[str, float] = {}
    completed: set[str] = set()
    dropped: set[str] = set()
    coin_spend = 0

    ordered = sorted(events, key=lambda e: e.ts)
    for e in ordered:
        w = EVENT_WEIGHT.get(e.type, 0.0)
        if e.type == "rate" and e.value is not None:
            w = (e.value - 3) * 0.6
        if e.type == "coin_unlock":
            coin_spend += e.coins or 0
        if e.type == "complete_series":
            completed.add(e.series_id)
        if e.type == "drop":
            dropped.add(e.series_id)
        series_weight[e.series_id] = series_weight.get(e.series_id, 0.0) + w

    dim = len(catalog[0].embedding) if catalog else 0
    taste_vector = [0.0] * dim
    genre_aff: dict[str, float] = {}
    lang_aff: dict[str, float] = {}
    tone_aff: dict[str, float] = {}
    pacing_aff: dict[str, float] = {}
    length_num = 0.0
    length_den = 0.0

    for series_id, weight in series_weight.items():
        s = by_id.get(series_id)
        if s is None or weight <= 0:  # only positive engagement shapes taste
            continue
        for i in range(dim):
            taste_vector[i] += weight * (s.embedding[i] if i < len(s.embedding) else 0.0)
        for g in s.genres:
            genre_aff[g] = genre_aff.get(g, 0.0) + weight
        for t in s.tone:
            tone_aff[t] = tone_aff.get(t, 0.0) + weight
        lang_aff[s.language] = lang_aff.get(s.language, 0.0) + weight
        pacing_aff[s.pacing] = pacing_aff.get(s.pacing, 0.0) + weight
        length_num += weight * s.avg_episode_minutes
        length_den += weight

    _normalize_vector(taste_vector)

    recent: list[str] = []
    for e in reversed(ordered):
        if e.series_id not in recent:
            recent.append(e.series_id)
        if len(recent) >= 8:
            break

    return TasteProfile(
        user_id=user_id,
        taste_vector=taste_vector,
        genre_affinity=_normalize_record(genre_aff),
        language_affinity=_normalize_record(lang_aff),
        tone_affinity=_normalize_record(tone_aff),
        pacing_affinity=_normalize_record(pacing_aff),
        avg_preferred_episode_minutes=(length_num / length_den) if length_den else 0.0,
        coin_spend=coin_spend,
        completed_series_ids=list(completed),
        dropped_series_ids=list(dropped),
        recent_series_ids=recent,
        event_count=len(events),
    )


def is_cold_start(profile: TasteProfile) -> bool:
    return profile.event_count < 3 or all(x == 0 for x in profile.taste_vector)


def _normalize_vector(vec: list[float]) -> None:
    mag = sum(v * v for v in vec) ** 0.5
    if mag == 0:
        return
    for i in range(len(vec)):
        vec[i] /= mag


def _normalize_record(record: dict[str, float]) -> dict[str, float]:
    """Scale so max value is 1 (keeps relative affinities intact)."""
    mx = max(record.values(), default=0.0)
    if mx == 0:
        return record
    return {k: max(0.0, v / mx) for k, v in record.items()}
