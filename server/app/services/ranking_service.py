"""Stage 2: deep ranking. Scores every candidate with the transparent feature
model and returns them sorted best-first, each carrying its score breakdown.
``weights`` is injectable so the data team can A/B different objectives."""
from __future__ import annotations

from app.domain.models import RankedSeries, TasteProfile
from app.domain.scoring import DEFAULT_WEIGHTS, RankingWeights, score_series
from app.services.candidate_service import Candidate


def rank_candidates(
    profile: TasteProfile,
    candidates: list[Candidate],
    weights: RankingWeights = DEFAULT_WEIGHTS,
) -> list[RankedSeries]:
    ranked = [
        RankedSeries(
            series=c.series,
            score=(bd := score_series(profile, c.series, c.content_similarity, weights)).total,
            breakdown=bd,
            sources=c.sources,
        )
        for c in candidates
    ]
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked
