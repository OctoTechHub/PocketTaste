"""Explanation layer.

The LLM never decides anything here. Scores, verdicts and drop-off points are all
computed upstream; this service only turns the already-computed numbers into plain
English. If the LLM is unavailable the deterministic sentence is returned instead,
and the response says which one it was.
"""

from __future__ import annotations

from app.core.config import Settings
from app.domain.models import (
    ContentFeatures,
    ContentItem,
    RecommendationResult,
    UserProfile,
)
from app.services.llm import LlmService

_RECOMMENDATION_PROMPT = """Explain a recommendation list to the listener.

Listener state (computed from their own event log):
- positive interactions: {positives}
- top genres: {genres}
- languages: {languages}
- pacing preference: {pacing}
- completion propensity: {completion}
- cold start: {cold_start}

Ranked results, each with its signal breakdown (weight x signal):
{items}

Ranker weights: {weights}

Write 2-3 sentences. Say why the top items surfaced, referencing the signals that
actually dominated. Use only these numbers. Do not invent titles or preferences."""

_DROPOFF_PROMPT = """Explain listener drop-off for one audio story to its creator.

Title: {title}
Runtime: {duration}s across {chapters} chapters
Listeners: {listeners} | plays: {plays} | completion rate: {completion}
Drop-off rate: {drop_off} | median abandon point: {abandon}s ({abandon_pct} of runtime)
Replay rate: {replay} | re-engagement rate: {re_engagement}

Retention curve (decile -> share of listeners still present):
{curve}

Chapter-level interest (0 = abandoned here, 1 = replayed here):
{chapters_detail}

Write 3-5 sentences: where listeners leave, which chapters hold or lose them, and
one concrete structural change. Cite only these numbers. If the sample size is
small ({listeners} listeners), say the read is provisional."""


class ExplanationService:
    def __init__(self, settings: Settings, llm: LlmService) -> None:
        self._settings = settings
        self._llm = llm

    async def explain_recommendations(
        self, result: RecommendationResult, user: UserProfile
    ) -> tuple[str, str]:
        """Returns (explanation, source)."""
        if not self._llm.available or not result.items:
            return result.explanation, "deterministic"

        rendered = "\n".join(
            f"{item.rank}. {item.title} [{item.language}, {'/'.join(item.genres) or 'general'}] "
            f"score={item.relevance_score} contributions={item.contributions}"
            for item in result.items[:8]
        )
        response = await self._llm.complete_text(
            _RECOMMENDATION_PROMPT.format(
                positives=len(user.positive_content_ids),
                genres=", ".join(sorted(user.genre_affinity, key=user.genre_affinity.get, reverse=True)[:4])
                or "none observed",
                languages=", ".join(user.language_affinity) or "none observed",
                pacing=user.pacing_preference.value,
                completion=user.completion_propensity,
                cold_start=user.is_cold_start,
                items=rendered,
                weights=result.weights,
            ),
            max_tokens=260,
        )
        if response.ok and response.text:
            return response.text, f"llm:{response.model}"
        return result.explanation, "deterministic"

    async def explain_drop_off(
        self, item: ContentItem, features: ContentFeatures
    ) -> tuple[str, str]:
        deterministic = self._deterministic_drop_off(item, features)
        if not self._llm.available or not features.retention_curve:
            return deterministic, "deterministic"

        curve = "\n".join(
            f"  {point.decile * 10}% ({point.position_seconds}s) -> {point.retained_ratio:.2f}"
            for point in features.retention_curve
        )
        chapters = "\n".join(
            f"  ch{row.chapter_index} '{row.title}': interest={row.interest_score:.2f}, "
            f"replays={row.replays}, drop_offs={row.drop_offs}, skips={row.skips}, listeners={row.listeners}"
            for row in features.chapter_interest
        ) or "  no chapter markers on this item"

        response = await self._llm.complete_text(
            _DROPOFF_PROMPT.format(
                title=item.title,
                duration=item.duration_seconds,
                chapters=len(item.chapters),
                listeners=features.unique_listeners,
                plays=features.plays,
                completion=features.completion_rate,
                drop_off=features.drop_off_rate,
                abandon=features.median_abandon_seconds,
                abandon_pct=(
                    f"{features.abandon_point_ratio:.0%}" if features.abandon_point_ratio else "n/a"
                ),
                replay=features.replay_rate,
                re_engagement=features.re_engagement_rate,
                curve=curve,
                chapters_detail=chapters,
            ),
            language=item.language,
            max_tokens=420,
        )
        if response.ok and response.text:
            return response.text, f"llm:{response.model}"
        return deterministic, "deterministic"

    @staticmethod
    def _deterministic_drop_off(item: ContentItem, features: ContentFeatures) -> str:
        if not features.retention_curve:
            return f"No retention data recorded for '{item.title}' yet."
        # The steepest decile-to-decile fall is the cliff worth reporting.
        worst_decile, worst_drop = 1, 0.0
        previous = 1.0
        for point in features.retention_curve:
            fall = previous - point.retained_ratio
            if fall > worst_drop:
                worst_decile, worst_drop = point.decile, fall
            previous = point.retained_ratio
        weakest = min(features.chapter_interest, key=lambda row: row.interest_score, default=None)
        chapter_note = (
            f" The weakest chapter is ch{weakest.chapter_index} '{weakest.title}' "
            f"(interest {weakest.interest_score:.2f}, {weakest.drop_offs} drop-offs)."
            if weakest
            else ""
        )
        return (
            f"'{item.title}' holds {features.retention_curve[-1].retained_ratio:.0%} of listeners to the end "
            f"across {features.unique_listeners} listeners. The steepest fall is at the "
            f"{worst_decile * 10}% mark, losing {worst_drop:.0%} of the remaining audience."
            f"{chapter_note} Completion rate is {features.completion_rate:.2f} and drop-off rate "
            f"{features.drop_off_rate:.2f} (confidence: {features.confidence.value})."
        )
