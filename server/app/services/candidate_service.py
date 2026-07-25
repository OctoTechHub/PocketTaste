"""Stage 1: candidate generation (fast, coarse).

Produces a few dozen plausible series from three complementary sources — content
(nearest neighbours to the taste vector), collaborative (item-item co-occurrence),
and popularity (cold-start / tail) — deduped, so the expensive ranker only scores
a small set. Completed and dropped series are always excluded.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import BehaviorEvent, CandidateSource, Series, TasteProfile
from app.domain.scoring import cosine


@dataclass
class Candidate:
    series: Series
    content_similarity: float
    sources: list[CandidateSource] = field(default_factory=list)


def build_cooccurrence(events: list[BehaviorEvent]) -> dict[str, dict[str, int]]:
    """Item->item co-occurrence over completed series ('finished X also finished Y')."""
    completed_by_user: dict[str, set[str]] = {}
    for e in events:
        if e.type != "complete_series":
            continue
        completed_by_user.setdefault(e.user_id, set()).add(e.series_id)

    co: dict[str, dict[str, int]] = {}
    for ids in completed_by_user.values():
        ids_list = list(ids)
        for a in ids_list:
            for b in ids_list:
                if a == b:
                    continue
                co.setdefault(a, {})
                co[a][b] = co[a].get(b, 0) + 1
    return co


def _norm_sim(sim: float) -> float:
    """Map cosine [-1,1] into a friendlier [0,1]."""
    return max(0.0, min(1.0, (sim + 1) / 2))


def generate_candidates(
    profile: TasteProfile,
    catalog: list[Series],
    cooccurrence: dict[str, dict[str, int]],
    limit: int = 40,
    exclude_ids: set[str] | None = None,
) -> list[Candidate]:
    excluded = set(profile.completed_series_ids) | set(profile.dropped_series_ids)
    if exclude_ids:
        excluded |= exclude_ids

    pool = [s for s in catalog if s.id not in excluded]
    merged: dict[str, Candidate] = {}

    def add(series: Series, source: CandidateSource, content_sim: float) -> None:
        existing = merged.get(series.id)
        if existing:
            if source not in existing.sources:
                existing.sources.append(source)
            existing.content_similarity = max(existing.content_similarity, content_sim)
        else:
            merged[series.id] = Candidate(series=series, content_similarity=content_sim, sources=[source])

    # Content: nearest neighbours to the taste vector.
    scored = sorted(
        ((s, cosine(profile.taste_vector, s.embedding)) for s in pool),
        key=lambda x: x[1],
        reverse=True,
    )
    for s, sim in scored[:limit]:
        add(s, "content", _norm_sim(sim))

    # Collaborative: series that co-occur with what the listener finished.
    collab: dict[str, int] = {}
    for seed in profile.completed_series_ids:
        for cid, count in cooccurrence.get(seed, {}).items():
            if cid in excluded:
                continue
            collab[cid] = collab.get(cid, 0) + count
    by_id = {s.id: s for s in pool}
    for cid, _ in sorted(collab.items(), key=lambda kv: kv[1], reverse=True)[:15]:
        s = by_id.get(cid)
        if s:
            add(s, "collaborative", _norm_sim(cosine(profile.taste_vector, s.embedding)))

    # Popularity: fills the tail and covers cold-start users.
    for s in sorted(pool, key=lambda x: x.popularity, reverse=True)[:10]:
        add(s, "popularity", _norm_sim(cosine(profile.taste_vector, s.embedding)))

    return list(merged.values())
