"""Ranker behaviour: score decomposition, MMR diversity, cold start, dedup suppression."""

from __future__ import annotations

import pytest
from conftest import make_item

from app.core.clock import days_ago
from app.domain.enums import DuplicateKind, Pacing
from app.domain.models import ContentProfile, UserProfile
from app.services.ranking import RankingContext, RankingService, build_suppression_set


def profile(content_id: str, embedding: list[float], **kwargs) -> ContentProfile:
    return ContentProfile(
        content_id=content_id, embedding=embedding, arc_embedding=embedding, **kwargs
    )


@pytest.fixture
def context():
    from app.domain.models import ContentFeatures

    catalog = {
        "fantasy_a": make_item("fantasy_a", title="Ashen Throne", genres=["fantasy"]),
        "fantasy_b": make_item("fantasy_b", title="Iron Realm", genres=["fantasy"]),
        "thriller_a": make_item("thriller_a", title="Silent Verdict", genres=["thriller"]),
        "romance_a": make_item("romance_a", title="Monsoon Vow", genres=["romance"], language="hi"),
    }
    profiles = {
        "fantasy_a": profile("fantasy_a", [1.0, 0.0, 0.0]),
        "fantasy_b": profile("fantasy_b", [0.98, 0.2, 0.0]),   # very close to fantasy_a
        "thriller_a": profile("thriller_a", [0.0, 1.0, 0.0]),
        "romance_a": profile("romance_a", [0.0, 0.0, 1.0]),
    }
    features = {
        cid: ContentFeatures(content_id=cid, plays=10, quality_score=0.5) for cid in catalog
    }
    return RankingContext(
        catalog=catalog, profiles=profiles, features=features, co_occurrence={}, total_plays=40
    )


@pytest.fixture
def ranker(settings):
    return RankingService(settings)


def test_contributions_sum_to_the_relevance_score(ranker, context):
    user = UserProfile(user_id="u1", taste_vector=[1.0, 0.0, 0.0], is_cold_start=False)
    result = ranker.recommend(user, context, limit=4)
    for item in result.items:
        assert round(sum(item.contributions.values()), 6) == item.relevance_score


def test_weights_are_published_with_every_response(ranker, context, settings):
    result = ranker.recommend(UserProfile(user_id="u1"), context, limit=2)
    assert result.weights == settings.ranking_weights.as_dict()
    assert round(sum(result.weights.values()), 6) == 1.0


def test_affinity_ranks_the_matching_genre_first(ranker, context):
    user = UserProfile(
        user_id="u1",
        taste_vector=[0.0, 1.0, 0.0],           # points at thriller_a
        genre_affinity={"thriller": 0.9, "fantasy": 0.1},
        language_affinity={"en": 1.0},
        positive_content_ids=["seen"],
        is_cold_start=False,
    )
    result = ranker.recommend(user, context, limit=4)
    assert result.items[0].content_id == "thriller_a"
    assert result.items[0].signals.affinity > 0.9


def test_already_interacted_items_are_excluded_unless_requested(ranker, context):
    user = UserProfile(user_id="u1", interacted_content_ids=["fantasy_a", "fantasy_b"])
    assert {i.content_id for i in ranker.recommend(user, context, limit=10).items} == {
        "thriller_a",
        "romance_a",
    }
    assert len(ranker.recommend(user, context, limit=10, include_seen=True).items) == 4


def test_language_filter_is_respected(ranker, context):
    result = ranker.recommend(UserProfile(user_id="u1"), context, limit=10, language="hi")
    assert [item.content_id for item in result.items] == ["romance_a"]


def test_mmr_lambda_zero_maximises_diversity(ranker, context):
    """With lambda=0 the selector ignores relevance entirely and only avoids redundancy,
    so the two near-identical fantasy items must not be adjacent picks."""
    user = UserProfile(user_id="u1", taste_vector=[1.0, 0.0, 0.0], is_cold_start=False)
    diverse = ranker.recommend(user, context, limit=2, diversity=0.0)
    picked = {item.content_id for item in diverse.items}
    assert picked != {"fantasy_a", "fantasy_b"}


def test_high_lambda_keeps_the_most_relevant_items(ranker, context):
    user = UserProfile(user_id="u1", taste_vector=[1.0, 0.0, 0.0], is_cold_start=False)
    greedy = ranker.recommend(user, context, limit=2, diversity=1.0)
    assert {item.content_id for item in greedy.items} == {"fantasy_a", "fantasy_b"}


def test_cold_start_still_returns_results_with_a_stated_strategy(ranker, context):
    result = ranker.recommend(UserProfile(user_id="new", is_cold_start=True), context, limit=3)
    assert len(result.items) == 3
    assert result.cold_start is True
    assert "cold" in result.strategy
    assert "Cold-start" in result.explanation
    assert all(item.signals.affinity == 0.0 for item in result.items)


def test_exploration_bonus_favours_under_observed_items(ranker, context):
    from app.domain.models import ContentFeatures

    context.features["fantasy_a"] = ContentFeatures(content_id="fantasy_a", plays=500)
    context.features["fantasy_b"] = ContentFeatures(content_id="fantasy_b", plays=0)
    context.total_plays = 500
    result = ranker.recommend(UserProfile(user_id="u1"), context, limit=4)
    scores = {item.content_id: item.signals.exploration for item in result.items}
    assert scores["fantasy_b"] > scores["fantasy_a"]


def test_freshness_decays_with_publication_age(ranker, context):
    context.catalog["fantasy_a"].published_at = days_ago(0)
    context.catalog["fantasy_b"].published_at = days_ago(365)
    result = ranker.recommend(UserProfile(user_id="u1"), context, limit=4)
    scores = {item.content_id: item.signals.freshness for item in result.items}
    assert scores["fantasy_a"] > scores["fantasy_b"]


def test_every_item_carries_a_human_readable_reason(ranker, context):
    result = ranker.recommend(UserProfile(user_id="u1"), context, limit=4)
    assert all(item.reason for item in result.items)
    assert all(item.rank == index for index, item in enumerate(result.items, start=1))


def test_empty_catalog_returns_an_explanation_not_a_crash(ranker):
    empty = RankingContext(catalog={}, profiles={}, features={}, co_occurrence={}, total_plays=0)
    result = ranker.recommend(UserProfile(user_id="u1"), empty, limit=5)
    assert result.items == []
    assert "No eligible catalog items" in result.explanation


# ---------------------------------------------------------------------------
# Duplicate suppression
# ---------------------------------------------------------------------------


def test_later_reupload_is_suppressed_and_the_original_survives():
    catalog = {
        "orig": make_item("orig", title="Ashen Throne", published_days_ago=100),
        "copy": make_item("copy", title="Ashen Throne Season 3", published_days_ago=5),
    }
    profiles = {
        "orig": profile(
            "orig",
            [1.0, 0.0],
            duplicate_kind=DuplicateKind.EXACT_DUPLICATE,
            nearest_neighbours=[{"content_id": "copy", "title": "copy", "score": 0.98}],
        ),
        "copy": profile(
            "copy",
            [1.0, 0.0],
            duplicate_kind=DuplicateKind.EXACT_DUPLICATE,
            nearest_neighbours=[{"content_id": "orig", "title": "orig", "score": 0.98}],
        ),
    }
    assert build_suppression_set(catalog, profiles) == {"copy"}


def test_near_duplicates_are_flagged_but_not_suppressed():
    """A near-duplicate is a 'review' verdict, so it stays rankable; only confirmed
    exact copies and series variants are withheld."""
    catalog = {
        "orig": make_item("orig", title="Ashen Throne", published_days_ago=100),
        "similar": make_item("similar", title="Iron Realm", published_days_ago=5),
    }
    profiles = {
        "orig": profile("orig", [1.0, 0.0]),
        "similar": profile(
            "similar",
            [1.0, 0.0],
            duplicate_kind=DuplicateKind.NEAR_DUPLICATE,
            nearest_neighbours=[{"content_id": "orig", "title": "orig", "score": 0.95}],
        ),
    }
    assert build_suppression_set(catalog, profiles) == set()


def test_suppressed_items_are_excluded_from_ranking_and_counted(ranker, context):
    context.profiles["fantasy_b"] = profile(
        "fantasy_b",
        [0.98, 0.2, 0.0],
        duplicate_kind=DuplicateKind.EXACT_DUPLICATE,
        nearest_neighbours=[{"content_id": "fantasy_a", "title": "a", "score": 0.99}],
    )
    context.catalog["fantasy_a"].published_at = days_ago(100)
    context.catalog["fantasy_b"].published_at = days_ago(1)
    context.suppressed = build_suppression_set(context.catalog, context.profiles)

    result = ranker.recommend(UserProfile(user_id="u1"), context, limit=10)
    assert "fantasy_b" not in {item.content_id for item in result.items}
    assert result.suppressed_duplicates == 1

    unfiltered = ranker.recommend(UserProfile(user_id="u1"), context, limit=10, include_duplicates=True)
    assert "fantasy_b" in {item.content_id for item in unfiltered.items}
