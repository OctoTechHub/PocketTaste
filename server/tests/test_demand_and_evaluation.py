"""Demand discovery and the offline evaluation harness."""

from __future__ import annotations

import pytest
from conftest import make_event, make_item

from app.core.clock import days_ago
from app.domain.enums import Confidence, EventType, Provenance
from app.domain.models import ContentFeatures, ContentProfile
from app.services.demand import DemandService
from app.services.evaluation import EvaluationService
from app.services.llm import LlmService
from app.services.ranking import RankingService


@pytest.fixture
def demand(settings):
    return DemandService(settings, LlmService(settings))


def _features(catalog):
    return {item.content_id: ContentFeatures(content_id=item.content_id, plays=5) for item in catalog}


# ---------------------------------------------------------------------------
# Demand discovery
# ---------------------------------------------------------------------------


async def test_under_supplied_segment_with_failed_searches_ranks_top(demand):
    """One thriller/hi item, heavy listening on it, plus searches the catalog cannot
    serve. That cell must surface as the opportunity."""
    catalog = [
        make_item("t_hi", genres=["thriller"], language="hi"),
        *[make_item(f"r_en_{i}", genres=["romance"], language="en") for i in range(8)],
    ]
    events = []
    for index in range(20):
        events += [
            make_event(f"u{index}", "t_hi", EventType.PLAY, session=f"s{index}"),
            make_event(f"u{index}", "t_hi", EventType.COMPLETE, position=3600, session=f"s{index}"),
        ]
    for index in range(30):
        events.append(
            make_event(f"q{index}", "r_en_0", EventType.SEARCH, session=f"qs{index}").model_copy(
                update={
                    "content_id": None,
                    "query": "हिंदी क्राइम थ्रिलर सीरीज",
                    "result_count": 0,
                }
            )
        )
    report = await demand.build_report(
        catalog, events, _features(catalog), {}, use_llm=False
    )
    top = report.segments[0]
    assert top.segment == "thriller/hi"
    assert top.opportunity_score > 0
    assert top.unmet_search_count == 30
    assert top.demand_share > top.supply_share


async def test_devanagari_and_named_language_searches_are_both_attributed(demand):
    catalog = [make_item("t_hi", genres=["thriller"], language="hi")]
    events = [
        make_event("u1", "t_hi", EventType.SEARCH).model_copy(
            update={"content_id": None, "query": "हिंदी थ्रिलर कहानी", "result_count": 0}
        ),
        make_event("u2", "t_hi", EventType.SEARCH, session="s2").model_copy(
            update={"content_id": None, "query": "hindi thriller full series", "result_count": 0}
        ),
    ]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    segment = next(row for row in report.segments if row.segment == "thriller/hi")
    assert segment.unmet_search_count == 2
    assert report.unattributed_unmet_searches == 0


async def test_multi_word_genre_slugs_are_matched_by_fragment(demand):
    """The real catalog uses slugs like 'crime-detective', which never appear as a
    single search token. Fragment matching is what keeps those searches countable."""
    catalog = [
        make_item("c_hi", genres=["crime-detective"], language="hi"),
        make_item("m_hi", genres=["mythology-fantasy"], language="hi"),
    ]
    events = [
        make_event("u1", "c_hi", EventType.SEARCH).model_copy(
            update={"content_id": None, "query": "hindi detective mystery audio", "result_count": 0}
        ),
        make_event("u2", "m_hi", EventType.SEARCH, session="s2").model_copy(
            update={"content_id": None, "query": "हिंदी पौराणिक कथा", "result_count": 0}
        ),
    ]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    by_segment = {row.segment: row for row in report.segments}
    assert by_segment["crime-detective/hi"].unmet_search_count == 1
    assert by_segment["mythology-fantasy/hi"].unmet_search_count == 1
    assert report.unattributed_unmet_searches == 0


async def test_hinglish_is_attributed_as_its_own_language(demand):
    catalog = [make_item("h_hing", genres=["horror"], language="hinglish")]
    events = [
        make_event("u1", "h_hing", EventType.SEARCH).model_copy(
            update={"content_id": None, "query": "hinglish horror story", "result_count": 0}
        )
    ]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    segment = next(row for row in report.segments if row.segment == "horror/hinglish")
    assert segment.unmet_search_count == 1
    assert report.unattributed_unmet_searches == 0


async def test_unattributable_searches_are_counted_never_guessed_into_a_segment(demand):
    catalog = [make_item("t_hi", genres=["thriller"], language="hi")]
    events = [
        make_event("u1", "t_hi", EventType.SEARCH).model_copy(
            update={"content_id": None, "query": "zzzz qqqq", "result_count": 0}
        )
    ]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    assert report.unattributed_unmet_searches == 1
    assert all(row.unmet_search_count == 0 for row in report.segments)


async def test_fully_synthetic_provenance_is_stated_loudly(demand):
    catalog = [make_item("c1")]
    catalog[0].is_synthetic = True
    events = [make_event("u1", "c1", EventType.PLAY, synthetic=True)]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    assert report.provenance is Provenance.SYNTHETIC_SIMULATION
    assert "SYNTHETIC" in report.data_notice
    assert "not real listeners" in report.data_notice.lower()


async def test_real_catalog_with_simulated_events_gets_its_own_label(demand):
    """The platform's real catalog plus a simulated event stream must not be reported
    as either fully real or fully synthetic."""
    catalog = [make_item("c1")]                       # real catalog item
    events = [make_event("u1", "c1", EventType.PLAY, synthetic=True)]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    assert report.provenance is Provenance.SIMULATED_FROM_REAL_CATALOG
    assert "REAL" in report.data_notice
    assert "SIMULATED" in report.data_notice
    assert "not real" in report.data_notice.lower()


async def test_real_events_are_not_labelled_synthetic(demand):
    catalog = [make_item("c1")]
    events = [make_event("u1", "c1", EventType.PLAY, synthetic=False)]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    assert report.provenance is Provenance.REAL


async def test_small_samples_are_marked_low_confidence(demand):
    catalog = [make_item("c1")]
    events = [make_event("u1", "c1", EventType.PLAY)]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    assert report.segments[0].confidence is Confidence.LOW


async def test_every_segment_carries_its_raw_evidence(demand):
    catalog = [make_item("c1")]
    events = [make_event("u1", "c1", EventType.PLAY)]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=False)
    evidence = report.segments[0].evidence
    assert {"catalog_items", "unique_listeners", "plays", "completions", "drop_offs"} <= set(evidence)


async def test_unplayed_patterns_are_not_called_over_supplied(demand):
    """A story nobody has played has a 0% completion rate. Dividing catalog share by
    that would brand every unreached story as over-supplied — reporting missing data
    as a damning verdict. Silence is not a bad review."""
    from app.domain.models import ContentProfile

    catalog = [make_item(f"c{i}", genres=["horror"]) for i in range(10)]
    profiles = {
        item.content_id: ContentProfile(content_id=item.content_id, narrative_pattern="haunted_house")
        for item in catalog
    }
    # Feature rows exist, but no one listened: plays recorded, zero unique listeners.
    features = {
        item.content_id: ContentFeatures(content_id=item.content_id, plays=0, unique_listeners=0)
        for item in catalog
    }
    report = await demand.build_report(catalog, [], features, profiles, use_llm=False)
    assert report.saturated_patterns == []


async def test_pattern_is_judged_once_enough_people_have_heard_it(demand, settings):
    from app.domain.models import ContentProfile

    catalog = [make_item(f"c{i}", genres=["horror"]) for i in range(10)]
    profiles = {
        item.content_id: ContentProfile(content_id=item.content_id, narrative_pattern="haunted_house")
        for item in catalog
    }
    features = {
        item.content_id: ContentFeatures(
            content_id=item.content_id,
            plays=20,
            unique_listeners=20,
            completion_rate=0.05,     # genuinely poor retention, genuinely measured
            drop_off_rate=0.95,
        )
        for item in catalog
    }
    report = await demand.build_report(catalog, [], features, profiles, use_llm=False)
    assert len(report.saturated_patterns) == 1
    row = report.saturated_patterns[0]
    assert row.narrative_pattern == "haunted_house"
    assert row.saturation_index > 1.0
    assert row.listeners >= settings.min_pattern_listeners
    assert row.measured_items == 10
    assert "over-supplied" in row.verdict


async def test_briefs_fall_back_to_deterministic_prose_without_an_llm(demand):
    catalog = [make_item("c1")]
    events = [make_event("u1", "c1", EventType.PLAY)]
    report = await demand.build_report(catalog, events, _features(catalog), {}, use_llm=True)
    assert report.briefs
    assert all(brief.generated_by.value == "heuristic" for brief in report.briefs)
    assert all(brief.supporting_metrics for brief in report.briefs)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@pytest.fixture
def evaluator(settings):
    return EvaluationService(settings, RankingService(settings))


def _learnable_dataset():
    """Twelve items in three genres; each user engages only within one genre, so the
    held-out item is predictable from taste — a signal a working ranker must recover."""
    genres = ["fantasy", "thriller", "romance"]
    catalog = [
        make_item(f"{genre}_{index}", genres=[genre], published_days_ago=30)
        for genre in genres
        for index in range(4)
    ]
    profiles = {}
    for position, item in enumerate(catalog):
        vector = [0.0, 0.0, 0.0]
        vector[genres.index(item.genres[0])] = 1.0
        vector[(genres.index(item.genres[0]) + 1) % 3] = 0.05 * (position % 4)
        profiles[item.content_id] = ContentProfile(
            content_id=item.content_id, embedding=vector, arc_embedding=vector
        )

    # Time is ordered item-major: every user consumes their 1st item, then their 2nd,
    # and so on. The final round therefore lands after the 80% split, giving each user
    # a genuinely unseen held-out item — which is what the evaluator needs to measure.
    events = []
    users = 30
    for item_index in range(4):
        for user_index in range(users):
            genre = genres[user_index % 3]
            content_id = f"{genre}_{item_index}"
            day = 30 - (item_index * users + user_index) * 0.02
            session = f"s{user_index}_{item_index}"
            events.append(
                make_event(f"u{user_index}", content_id, EventType.PLAY, session=session, days=day)
            )
            events.append(
                make_event(
                    f"u{user_index}",
                    content_id,
                    EventType.COMPLETE,
                    position=3600,
                    session=session,
                    days=day,
                )
            )
    events.sort(key=lambda event: event.occurred_at)
    return catalog, events, profiles


def test_hybrid_beats_popularity_on_a_learnable_dataset(evaluator):
    catalog, events, profiles = _learnable_dataset()
    report = evaluator.evaluate(catalog, events, profiles, k=4, min_interactions=2)

    assert report.users_evaluated > 0
    results = {row.strategy: row for row in report.results}
    assert set(results) == {"hybrid_mmr", "popularity_baseline", "random_baseline"}
    assert results["hybrid_mmr"].recall_at_k >= results["popularity_baseline"].recall_at_k
    assert results["hybrid_mmr"].ndcg_at_k >= results["popularity_baseline"].ndcg_at_k


def test_metrics_stay_inside_their_valid_ranges(evaluator):
    catalog, events, profiles = _learnable_dataset()
    report = evaluator.evaluate(catalog, events, profiles, k=4, min_interactions=2)
    for row in report.results:
        for metric in (row.recall_at_k, row.precision_at_k, row.ndcg_at_k, row.mrr, row.hit_rate):
            assert 0.0 <= metric <= 1.0
        assert 0.0 <= row.catalog_coverage <= 1.0


def test_split_is_temporal_and_reported(evaluator):
    catalog, events, profiles = _learnable_dataset()
    report = evaluator.evaluate(catalog, events, profiles, k=4, min_interactions=2)
    assert report.train_events > report.test_events
    assert report.train_events + report.test_events == len(events)
    assert report.split_at
    assert "temporal holdout" in report.method


def test_synthetic_data_is_disclosed_in_the_caveats(evaluator):
    catalog, events, profiles = _learnable_dataset()
    report = evaluator.evaluate(catalog, events, profiles, k=4, min_interactions=2)
    assert any("SYNTHETIC" in caveat for caveat in report.caveats)


def test_thin_data_skips_evaluation_instead_of_reporting_a_number(evaluator):
    catalog = [make_item("c1"), make_item("c2")]
    events = [make_event("u1", "c1", EventType.PLAY)]
    report = evaluator.evaluate(catalog, events, {}, k=10)
    assert report.results == []
    assert report.users_evaluated == 0
    assert "skipped" in report.caveats[0]
