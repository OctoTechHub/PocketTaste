"""Pure ranking math. No IO.

This is the "Stage 2" ranker: given a taste profile and a candidate series it
produces a transparent, weighted score. In production this stage would be a
Merlin DLRM / deep CTR model trained to predict completion + coin-unlock. Here we
use an interpretable linear model over the same features so every recommendation
is explainable and the weights are trivially A/B-testable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.domain.models import ScoreBreakdown, Series, TasteProfile


@dataclass(frozen=True)
class RankingWeights:
    content_similarity: float = 0.30
    genre_affinity: float = 0.18
    language_match: float = 0.12
    tone_match: float = 0.10
    pacing_match: float = 0.06
    length_fit: float = 0.06
    monetization_proxy: float = 0.12
    freshness: float = 0.06


# Default objective: bias toward completion + monetization, not raw clicks.
DEFAULT_WEIGHTS = RankingWeights()

_PACING_ORDER = {"slow-burn": 0, "medium": 1, "fast": 2}


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; 0 when either vector is empty/zero."""
    if not a or not b:
        return 0.0
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def clamp01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return max(0.0, min(1.0, x))


def top_key(record: dict[str, float]) -> str | None:
    if not record:
        return None
    return max(record.items(), key=lambda kv: kv[1])[0]


def _pacing_match(profile: TasteProfile, series: Series) -> float:
    affinity = profile.pacing_affinity.get(series.pacing, 0.0)
    preferred = top_key(profile.pacing_affinity)
    if preferred is None:
        return affinity
    distance = abs(_PACING_ORDER[series.pacing] - _PACING_ORDER[preferred])
    closeness = 1 - distance / 2
    return 0.5 * affinity + 0.5 * closeness


def _length_fit(profile: TasteProfile, series: Series) -> float:
    if not profile.avg_preferred_episode_minutes:
        return 0.5
    diff = abs(series.avg_episode_minutes - profile.avg_preferred_episode_minutes)
    return clamp01(1 - diff / 30)


def _monetization_proxy(profile: TasteProfile, series: Series, genre_affinity: float) -> float:
    """Estimated willingness to spend coins: heavy spenders + strong genre match
    + comfortable price => higher. People pay to finish stories they're hooked on."""
    spend_propensity = clamp01(profile.coin_spend / 500)
    price_comfort = clamp01(1 - series.coin_price_approx / 600)
    return clamp01(0.5 * spend_propensity + 0.3 * genre_affinity + 0.2 * price_comfort)


def _freshness(series: Series) -> float:
    f = series.popularity * 0.5
    if series.is_new:
        f += 0.3
    if series.is_original:
        f += 0.2
    return clamp01(f)


def _genre_affinity(profile: TasteProfile, series: Series) -> float:
    if not series.genres:
        return 0.0
    total = sum(profile.genre_affinity.get(g, 0.0) for g in series.genres)
    return clamp01(total / len(series.genres))


def _tone_affinity(profile: TasteProfile, series: Series) -> float:
    if not series.tone:
        return 0.0
    total = sum(profile.tone_affinity.get(t, 0.0) for t in series.tone)
    return clamp01(total / len(series.tone))


def score_series(
    profile: TasteProfile,
    series: Series,
    content_similarity: float,
    weights: RankingWeights = DEFAULT_WEIGHTS,
) -> ScoreBreakdown:
    """Score a single candidate. ``content_similarity`` (0..1) is precomputed
    against the taste vector by the candidate stage."""
    genre = _genre_affinity(profile, series)
    language = clamp01(profile.language_affinity.get(series.language, 0.0))
    tone = _tone_affinity(profile, series)
    pacing = _pacing_match(profile, series)
    length = _length_fit(profile, series)
    money = _monetization_proxy(profile, series, genre)
    fresh = _freshness(series)
    content = clamp01(content_similarity)

    total = (
        weights.content_similarity * content
        + weights.genre_affinity * genre
        + weights.language_match * language
        + weights.tone_match * tone
        + weights.pacing_match * pacing
        + weights.length_fit * length
        + weights.monetization_proxy * money
        + weights.freshness * fresh
    )

    return ScoreBreakdown(
        content_similarity=content,
        genre_affinity=genre,
        language_match=language,
        tone_match=tone,
        pacing_match=pacing,
        length_fit=length,
        monetization_proxy=money,
        freshness=fresh,
        total=total,
    )
