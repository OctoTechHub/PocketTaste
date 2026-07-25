"""The feature builder is the foundation of every creator-facing number, so its
arithmetic is pinned here rather than assumed."""

from __future__ import annotations

from conftest import make_event, make_item

from app.domain.enums import Confidence, EventType, Pacing, Provenance
from app.services.feature_builder import (
    build_co_occurrence,
    build_content_features,
    build_user_profile,
)


def test_completion_and_drop_off_rates_are_computed_per_play():
    item = make_item("c1", duration=1000, chapters=5)
    events = [
        make_event("u1", "c1", EventType.PLAY),
        make_event("u1", "c1", EventType.COMPLETE, position=1000),
        make_event("u2", "c1", EventType.PLAY, session="s2"),
        make_event("u2", "c1", EventType.DROP_OFF, position=200, session="s2"),
    ]
    features = build_content_features(item, events)

    assert features.plays == 2
    assert features.unique_listeners == 2
    assert features.completions == 1
    assert features.completion_rate == 0.5
    assert features.drop_off_rate == 0.5
    assert features.median_abandon_seconds == 200
    assert features.abandon_point_ratio == 0.2


def test_retention_curve_counts_completers_as_reaching_the_end():
    item = make_item("c1", duration=1000, chapters=5)
    events = [
        make_event("u1", "c1", EventType.PLAY),
        make_event("u1", "c1", EventType.COMPLETE, position=0),  # position ignored on complete
        make_event("u2", "c1", EventType.PLAY, session="s2"),
        make_event("u2", "c1", EventType.DROP_OFF, position=500, session="s2"),
    ]
    curve = build_content_features(item, events).retention_curve

    assert len(curve) == 10
    assert curve[0].retained_ratio == 1.0    # both listeners passed 10%
    assert curve[4].retained_ratio == 1.0    # u2 reached exactly 500 = the 50% mark
    assert curve[9].retained_ratio == 0.5    # only the completer reached 100%


def test_retention_curve_is_monotonically_non_increasing():
    item = make_item("c1", duration=1000, chapters=5)
    events = [make_event("u1", "c1", EventType.PLAY)]
    for index, position in enumerate([100, 250, 400, 900]):
        events.append(
            make_event(f"u{index + 2}", "c1", EventType.DROP_OFF, position=position, session=f"s{index}")
        )
    curve = build_content_features(item, events).retention_curve
    ratios = [point.retained_ratio for point in curve]
    assert ratios == sorted(ratios, reverse=True)


def test_chapter_interest_separates_replayed_from_abandoned_chapters():
    item = make_item("c1", duration=600, chapters=6)  # 100s chapters
    events = [make_event("u1", "c1", EventType.PLAY)]
    # Chapter 1 gets replayed by three listeners; chapter 4 loses three listeners.
    for index in range(3):
        events.append(
            make_event(f"u{index}", "c1", EventType.REPLAY, position=110, chapter=1, session=f"r{index}")
        )
        events.append(
            make_event(f"v{index}", "c1", EventType.DROP_OFF, position=410, chapter=4, session=f"d{index}")
        )
    interest = {row.chapter_index: row for row in build_content_features(item, events).chapter_interest}

    assert interest[1].replays == 3
    assert interest[4].drop_offs == 3
    assert interest[1].interest_score > interest[4].interest_score
    assert 0.0 <= interest[4].interest_score <= 1.0


def test_re_engagement_counts_listeners_returning_in_a_later_session():
    item = make_item("c1")
    events = [
        make_event("u1", "c1", EventType.PLAY, session="a"),
        make_event("u1", "c1", EventType.PLAY, session="b"),   # returned
        make_event("u2", "c1", EventType.PLAY, session="c"),   # did not
    ]
    assert build_content_features(item, events).re_engagement_rate == 0.5


def test_confidence_scales_with_sample_size():
    item = make_item("c1")
    small = build_content_features(item, [make_event("u1", "c1", EventType.PLAY)])
    assert small.confidence is Confidence.LOW

    many = [
        make_event(f"u{index}", "c1", EventType.PLAY, session=f"s{index}", synthetic=False)
        for index in range(40)
    ]
    assert build_content_features(item, many, min_confident_sample_size=30).confidence is Confidence.HIGH


def test_provenance_distinguishes_a_real_catalog_from_an_invented_one():
    """A real story with a simulated event log is a different claim from a fully
    invented dataset, and the two must not collapse to the same label."""
    real_item = make_item("c1")                       # is_synthetic defaults to False
    synthetic_item = make_item("c2")
    synthetic_item.is_synthetic = True

    real_events = [make_event("u1", "c1", EventType.PLAY, synthetic=False)]
    fake_events = [make_event("u1", "c1", EventType.PLAY, synthetic=True)]

    assert build_content_features(real_item, real_events).provenance is Provenance.REAL
    assert (
        build_content_features(real_item, fake_events).provenance
        is Provenance.SIMULATED_FROM_REAL_CATALOG
    )
    assert (
        build_content_features(synthetic_item, fake_events).provenance
        is Provenance.SYNTHETIC_SIMULATION
    )
    mixed = build_content_features(real_item, real_events + fake_events)
    assert mixed.provenance is Provenance.MIXED


def test_empty_event_log_produces_zeros_not_errors():
    features = build_content_features(make_item("c1"), [])
    assert features.plays == 0
    assert features.completion_rate == 0.0
    assert features.retention_curve == []
    assert features.median_abandon_seconds is None


# ---------------------------------------------------------------------------
# User profiles
# ---------------------------------------------------------------------------


def test_taste_vector_and_affinities_follow_positive_interactions(catalog):
    catalog_by_id = {item.content_id: item for item in catalog}
    profiles = {
        "c1": _profile("c1", [1.0, 0.0, 0.0]),
        "c2": _profile("c2", [0.0, 1.0, 0.0]),
        "c3": _profile("c3", [0.0, 0.0, 1.0]),
    }
    events = [
        make_event("u1", "c2", EventType.PLAY),
        make_event("u1", "c2", EventType.COMPLETE, position=3600),
        make_event("u1", "c2", EventType.REPLAY, position=100),
    ]
    profile = build_user_profile("u1", events, catalog_by_id, profiles, catalog_median_duration=3600)

    assert profile.positive_content_ids == ["c2"]
    assert profile.taste_vector[1] == max(profile.taste_vector)  # pulled toward c2
    assert max(profile.genre_affinity, key=profile.genre_affinity.get) == "thriller"
    assert profile.completion_propensity == 1.0


def test_early_abandon_is_weighted_more_negatively_than_a_late_one(catalog):
    catalog_by_id = {item.content_id: item for item in catalog}
    profiles = {"c1": _profile("c1", [1.0, 0.0, 0.0])}

    early = build_user_profile(
        "u_early",
        [make_event("u_early", "c1", EventType.DROP_OFF, position=100)],
        catalog_by_id,
        profiles,
        catalog_median_duration=3600,
    )
    late = build_user_profile(
        "u_late",
        [make_event("u_late", "c1", EventType.DROP_OFF, position=3400)],
        catalog_by_id,
        profiles,
        catalog_median_duration=3600,
    )
    assert early.genre_affinity  # both produced affinities
    assert early.avg_abandon_ratio is not None and late.avg_abandon_ratio is not None
    assert early.avg_abandon_ratio < late.avg_abandon_ratio


def test_cold_start_requires_fewer_than_two_positive_items(catalog):
    catalog_by_id = {item.content_id: item for item in catalog}
    profiles = {item.content_id: _profile(item.content_id, [1.0, 0.0, 0.0]) for item in catalog}

    one = build_user_profile(
        "u1",
        [make_event("u1", "c1", EventType.COMPLETE, position=10)],
        catalog_by_id,
        profiles,
        catalog_median_duration=3600,
    )
    two = build_user_profile(
        "u2",
        [
            make_event("u2", "c1", EventType.COMPLETE, position=10),
            make_event("u2", "c2", EventType.COMPLETE, position=10, session="s2"),
        ],
        catalog_by_id,
        profiles,
        catalog_median_duration=3600,
    )
    assert one.is_cold_start is True
    assert two.is_cold_start is False


def test_pacing_is_inferred_from_completed_durations(catalog):
    catalog_by_id = {item.content_id: item for item in catalog}
    profiles = {"c1": _profile("c1", [1.0, 0.0, 0.0])}
    events = [make_event("u1", "c1", EventType.COMPLETE, position=3600)]

    slow = build_user_profile("u1", events, catalog_by_id, profiles, catalog_median_duration=1000)
    fast = build_user_profile("u1", events, catalog_by_id, profiles, catalog_median_duration=9000)
    assert slow.pacing_preference is Pacing.SLOW
    assert fast.pacing_preference is Pacing.FAST


# ---------------------------------------------------------------------------
# Co-occurrence
# ---------------------------------------------------------------------------


def test_co_occurrence_is_symmetric_and_normalised_by_popularity():
    matrix = build_co_occurrence([["a", "b"], ["a", "b"], ["a", "c"]])
    assert matrix["a"]["b"] == matrix["b"]["a"]
    # a and b co-occur twice out of |a|=3, |b|=2 -> 2/sqrt(6) ~= 0.8165
    assert round(matrix["a"]["b"], 3) == 0.816
    # a is more popular than c, so the pair is discounted relative to a raw co-count.
    assert matrix["a"]["c"] < matrix["a"]["b"]


def test_co_occurrence_ignores_single_item_baskets():
    assert build_co_occurrence([["a"], ["b"]]) == {}


def _profile(content_id: str, embedding: list[float]):
    from app.domain.models import ContentProfile

    return ContentProfile(content_id=content_id, embedding=embedding, arc_embedding=embedding)
