"""Turn domain objects into lean client payloads.

Notably strips the (256/1536-float) embedding vectors — the client never needs
them and they bloat responses.
"""
from __future__ import annotations

from app.domain.models import FeedRail, RankedSeries, Series, TasteProfile
from app.domain.scoring import top_key


def public_series(s: Series) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "synopsis": s.synopsis,
        "genres": s.genres,
        "language": s.language,
        "tone": s.tone,
        "pacing": s.pacing,
        "episodeCount": s.episode_count,
        "avgEpisodeMinutes": s.avg_episode_minutes,
        "narrator": s.narrator,
        "isOriginal": s.is_original,
        "isNew": s.is_new,
        "popularity": round(s.popularity, 3),
        "coinPriceApprox": s.coin_price_approx,
        "tags": s.tags,
    }


def public_ranked(r: RankedSeries) -> dict:
    bd = r.breakdown
    return {
        "series": public_series(r.series),
        "score": round(r.score, 4),
        "sources": r.sources,
        "reason": r.reason,
        "breakdown": {
            "contentSimilarity": round(bd.content_similarity, 3),
            "genreAffinity": round(bd.genre_affinity, 3),
            "languageMatch": round(bd.language_match, 3),
            "toneMatch": round(bd.tone_match, 3),
            "pacingMatch": round(bd.pacing_match, 3),
            "lengthFit": round(bd.length_fit, 3),
            "monetizationProxy": round(bd.monetization_proxy, 3),
            "freshness": round(bd.freshness, 3),
            "total": round(bd.total, 4),
        },
    }


def public_rail(rail: FeedRail) -> dict:
    return {
        "key": rail.key,
        "title": rail.title,
        "subtitle": rail.subtitle,
        "items": [public_ranked(i) for i in rail.items],
    }


def public_profile(p: TasteProfile) -> dict:
    return {
        "userId": p.user_id,
        "eventCount": p.event_count,
        "coinSpend": p.coin_spend,
        "topGenre": top_key(p.genre_affinity),
        "topTone": top_key(p.tone_affinity),
        "topLanguage": top_key(p.language_affinity),
        "avgPreferredEpisodeMinutes": round(p.avg_preferred_episode_minutes, 1),
        "genreAffinity": {k: round(v, 3) for k, v in p.genre_affinity.items()},
        "toneAffinity": {k: round(v, 3) for k, v in p.tone_affinity.items()},
        "languageAffinity": {k: round(v, 3) for k, v in p.language_affinity.items()},
        "completedSeriesIds": p.completed_series_ids,
        "droppedSeriesIds": p.dropped_series_ids,
        "recentSeriesIds": p.recent_series_ids,
    }
