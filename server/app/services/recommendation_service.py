"""Assembles the personalized home feed as a set of themed rails.

Runs the full 3-stage pipeline (taste -> candidates -> ranking) then slices the
ranked pool into rails: For You, Because-you-finished, coin-worthy binges, and
new-and-rising. Home-feed explanations use the fast deterministic templates; the
LLM is reserved for the conversational discovery + /explain endpoints.
"""
from __future__ import annotations

from app.domain.models import FeedRail, RankedSeries, Series, TasteProfile
from app.domain.scoring import cosine, top_key
from app.services.candidate_service import generate_candidates
from app.services.context_service import get_catalog, get_cooccurrence
from app.services.explain_service import attach_explanations
from app.services.ranking_service import rank_candidates
from app.services.taste_service import build_taste_profile, is_cold_start
from app.data.repositories import event_repository

RAIL_SIZE = 10


def build_profile(user_id: str) -> tuple[TasteProfile, list[Series]]:
    catalog = get_catalog()
    events = event_repository.find_by_user(user_id)
    profile = build_taste_profile(user_id, events, catalog)
    return profile, catalog


def build_feed(user_id: str) -> list[FeedRail]:
    profile, catalog = build_profile(user_id)
    cooccurrence = get_cooccurrence()
    candidates = generate_candidates(profile, catalog, cooccurrence, limit=60)
    ranked = rank_candidates(profile, candidates)
    attach_explanations(profile, ranked, catalog, use_llm=False)

    rails: list[FeedRail] = []
    used: set[str] = set()

    def take(items: list[RankedSeries], n: int) -> list[RankedSeries]:
        out: list[RankedSeries] = []
        for it in items:
            if it.series.id in used:
                continue
            out.append(it)
            used.add(it.series.id)
            if len(out) >= n:
                break
        return out

    # 1. For You — the headline personalized rail.
    for_you = take(ranked, RAIL_SIZE)
    if for_you:
        subtitle = (
            "Cold start — trending picks while we learn your taste"
            if is_cold_start(profile)
            else "Ranked for completion & coins, not just clicks"
        )
        rails.append(FeedRail(key="for_you", title="For You", subtitle=subtitle, items=for_you))

    # 2. Because you finished {most recent completed series}.
    seed = _most_recent_completed(profile, catalog)
    if seed is not None:
        similar = _similar_to(seed, ranked)
        picks = take(similar, RAIL_SIZE)
        if picks:
            rails.append(
                FeedRail(
                    key="because_finished",
                    title=f"Because you finished {seed.title}",
                    subtitle="Same narrative DNA",
                    items=picks,
                )
            )

    # 3. Coin-worthy binges — monetization-forward ordering.
    money = sorted(ranked, key=lambda r: r.breakdown.monetization_proxy, reverse=True)
    money_picks = take(money, RAIL_SIZE)
    if money_picks:
        rails.append(
            FeedRail(
                key="coin_worthy",
                title="Coin-worthy binges",
                subtitle="Long arcs you're likely to unlock",
                items=money_picks,
            )
        )

    # 4. New & rising in the listener's top language.
    lang = top_key(profile.language_affinity)
    new_items = [r for r in ranked if r.series.is_new and (lang is None or r.series.language == lang)]
    new_picks = take(new_items or [r for r in ranked if r.series.is_new], RAIL_SIZE)
    if new_picks:
        where = f" in {lang}" if lang else ""
        rails.append(
            FeedRail(
                key="new_rising",
                title=f"New & rising{where}",
                subtitle="Fresh originals gaining momentum",
                items=new_picks,
            )
        )

    return rails


def similar_series(series_id: str, limit: int = 8) -> list[RankedSeries]:
    catalog = get_catalog()
    target = next((s for s in catalog if s.id == series_id), None)
    if target is None:
        return []
    scored = sorted(
        (s for s in catalog if s.id != series_id),
        key=lambda s: cosine(target.embedding, s.embedding),
        reverse=True,
    )[:limit]
    from app.domain.scoring import score_series

    out: list[RankedSeries] = []
    for s in scored:
        sim = max(0.0, cosine(target.embedding, s.embedding))
        bd = score_series(TasteProfile(user_id="_"), s, sim)
        bd.total = sim
        out.append(RankedSeries(series=s, score=sim, breakdown=bd, sources=["content"]))
    return out


def _most_recent_completed(profile: TasteProfile, catalog: list[Series]) -> Series | None:
    by_id = {s.id: s for s in catalog}
    for sid in profile.recent_series_ids:
        if sid in profile.completed_series_ids and sid in by_id:
            return by_id[sid]
    # fall back to any completed
    for sid in profile.completed_series_ids:
        if sid in by_id:
            return by_id[sid]
    return None


def _similar_to(seed: Series, ranked: list[RankedSeries]) -> list[RankedSeries]:
    return sorted(
        ranked,
        key=lambda r: cosine(seed.embedding, r.series.embedding),
        reverse=True,
    )
