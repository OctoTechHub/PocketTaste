"""Stage 3: conversational / mood-first discovery.

A natural-language request ("dark office romance, Hindi, 15-min episodes, no
horror") is parsed into a structured intent, used to hard-filter the catalog,
then ranked by a blend of *query similarity* (semantic match to the request) and
*personalization* (the same Stage-2 feature score), and finally explained.
"""
from __future__ import annotations

from app.config import settings
from app.domain.models import DiscoveryIntent, RankedSeries, Series, TasteProfile
from app.domain.scoring import cosine, score_series
from app.services.ai.embeddings import embed_text
from app.services.ai.llm import parse_discovery_query
from app.services.explain_service import attach_explanations


def _intent_document(intent: DiscoveryIntent) -> str:
    """Mirror of series_document weighting so the query vector lands near matches."""
    parts = [
        intent.mood_text,
        " ".join(intent.genres * 8),
        " ".join(intent.tones * 6),
        (intent.language + " ") * 6 if intent.language else "",
        (intent.pacing + " ") * 3 if intent.pacing else "",
        " ".join(intent.keywords),
    ]
    return " . ".join(p for p in parts if p)


def _passes_hard_filters(s: Series, intent: DiscoveryIntent) -> bool:
    if intent.language and s.language != intent.language:
        return False
    if any(g in s.genres for g in intent.exclude_genres):
        return False
    if intent.max_episode_minutes and s.avg_episode_minutes > intent.max_episode_minutes + 2:
        return False
    return True


def discover(
    user_id: str | None,
    query: str,
    profile: TasteProfile,
    catalog: list[Series],
    limit: int = 12,
) -> tuple[list[RankedSeries], DiscoveryIntent]:
    intent = parse_discovery_query(query)
    query_vec = embed_text(_intent_document(intent))

    filtered = [s for s in catalog if _passes_hard_filters(s, intent)]
    # If filters are too aggressive and nothing matches, relax to the full catalog.
    pool = filtered or catalog

    exclude = set(profile.completed_series_ids) | set(profile.dropped_series_ids)

    ranked: list[RankedSeries] = []
    for s in pool:
        if s.id in exclude:
            continue
        query_sim = max(0.0, cosine(query_vec, s.embedding))
        # Soft intent boosts for explicitly requested genres/tones.
        boost = 0.0
        if intent.genres and any(g in s.genres for g in intent.genres):
            boost += 0.1
        if intent.tones and any(t in s.tone for t in intent.tones):
            boost += 0.05
        personal = score_series(profile, s, query_sim).total
        final = 0.6 * query_sim + 0.4 * personal + boost
        bd = score_series(profile, s, query_sim)
        bd.total = final
        ranked.append(RankedSeries(series=s, score=final, breakdown=bd, sources=["query"]))

    ranked.sort(key=lambda r: r.score, reverse=True)
    top = ranked[:limit]
    attach_explanations(profile, top, catalog, use_llm=settings.has_openai)
    return top, intent
