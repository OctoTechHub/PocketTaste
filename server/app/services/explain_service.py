"""'Explain Why I Will Love This.' Produces a human sentence per recommendation.

A deterministic template is always computed from the score breakdown; when an LLM
is available it rewrites that into something warmer, but never loses the grounding
facts.
"""
from __future__ import annotations

from app.domain.models import RankedSeries, Series, TasteProfile
from app.domain.scoring import top_key
from app.services.ai.llm import write_explanation


def summarize_taste(profile: TasteProfile, catalog: list[Series]) -> str:
    by_id = {s.id: s for s in catalog}
    top_genre = top_key(profile.genre_affinity)
    top_tone = top_key(profile.tone_affinity)
    top_lang = top_key(profile.language_affinity)
    finished = [by_id[i].title for i in profile.completed_series_ids if i in by_id][:3]

    parts: list[str] = []
    if finished:
        parts.append(f"finished {', '.join(finished)}")
    if top_genre:
        parts.append(f"loves {top_genre}")
    if top_tone:
        parts.append(f"{top_tone} tone")
    if top_lang:
        parts.append(f"{top_lang} audio")
    if profile.avg_preferred_episode_minutes:
        parts.append(f"~{round(profile.avg_preferred_episode_minutes)}-min episodes")
    return "; ".join(parts) or "new listener, still learning their taste"


def fallback_explanation(profile: TasteProfile, ranked: RankedSeries) -> str:
    """Grounded template — used as-is with no LLM, and as the LLM's anchor."""
    s = ranked.series
    bd = ranked.breakdown
    reasons: list[str] = []
    top_genre = top_key(profile.genre_affinity)

    if "collaborative" in ranked.sources:
        reasons.append("listeners who finished the same series binged this next")
    if bd.content_similarity > 0.6 and top_genre and top_genre in s.genres:
        reasons.append(f"it matches your taste for {top_genre}")
    elif bd.genre_affinity > 0.5:
        reasons.append(f"it leans into {' & '.join(s.genres[:2])}")
    if bd.language_match > 0.6:
        reasons.append(f"it's in {s.language}")
    if bd.length_fit > 0.7:
        reasons.append("episodes are the length you finish")
    if bd.freshness > 0.6 and s.is_new:
        reasons.append("it just launched")

    because = ", and ".join(reasons[:2]) if reasons else "it fits your recent listening"
    return f"Recommended because {because}."


def attach_explanations(
    profile: TasteProfile,
    ranked: list[RankedSeries],
    catalog: list[Series],
    use_llm: bool,
) -> list[RankedSeries]:
    context_summary = summarize_taste(profile, catalog)
    for item in ranked:
        fallback = fallback_explanation(profile, item)
        if not use_llm:
            item.reason = fallback
            continue
        facts = (
            f"{'/'.join(item.series.genres)}, {'/'.join(item.series.tone)}, "
            f"{item.series.language}, {item.series.avg_episode_minutes}-min episodes"
        )
        item.reason = write_explanation(context_summary, item.series.title, facts, fallback)
    return ranked
