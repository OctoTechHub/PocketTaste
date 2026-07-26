"""The two-listener blend. Pure scoring — no database, no LLM."""

from __future__ import annotations

import pytest
from conftest import make_item

from app.domain.models import ContentFeatures, UserProfile
from app.services.blend import (
    DEFAULT_ALPHA,
    BlendMember,
    BlendService,
    _normalise,
    taste_match,
)
from app.services.ranking import RankingContext, RankingService


def member(user_id: str, name: str, **profile_kwargs) -> BlendMember:
    return BlendMember(
        user_id=user_id,
        display_name=name,
        email=f"{name.lower()}@example.com",
        profile=UserProfile(user_id=user_id, **profile_kwargs),
    )


@pytest.fixture
def context() -> RankingContext:
    items = {
        f"c{index}": make_item(
            f"c{index}",
            title=f"Story {index}",
            genres=["horror"] if index % 2 else ["romance"],
        )
        for index in range(12)
    }
    return RankingContext(
        catalog=items,
        profiles={},
        features={cid: ContentFeatures(content_id=cid) for cid in items},
        co_occurrence={},
        total_plays=100,
    )


@pytest.fixture
def service(settings) -> BlendService:
    return BlendService(settings, RankingService(settings))


# ---------------------------------------------------------------------------
# Normalisation — the step that stops the heavier listener taking the feed
# ---------------------------------------------------------------------------


def test_normalisation_makes_two_listeners_comparable():
    """A heavy listener's raw scores are larger across the board. Compared directly,
    every item looks like theirs; rescaled against each listener's own spread, the
    same relative preferences survive and become comparable."""
    heavy = {"a": 0.60, "b": 0.50, "c": 0.40}
    light = {"a": 0.12, "b": 0.22, "c": 0.32}

    assert min(heavy.values()) > max(light.values())      # no overlap at all

    nh, nl = _normalise(heavy), _normalise(light)
    assert (nh["a"], nh["c"]) == (1.0, 0.0)
    assert (nl["c"], nl["a"]) == (1.0, 0.0)
    # Their disagreement is now visible instead of hidden by scale.
    assert nh["a"] > nl["a"] and nl["c"] > nh["c"]


def test_a_listener_with_no_opinion_neither_vetoes_nor_drives():
    """A cold-start member scores everything identically. Dividing by a zero spread
    would blow up; treating them as 0.5 everywhere lets the other member lead."""
    assert _normalise({"a": 0.3, "b": 0.3}) == {"a": 0.5, "b": 0.5}


def test_normalisation_of_nothing_is_nothing():
    assert _normalise({}) == {}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_least_misery_sinks_an_item_one_member_rejects():
    """The reason the blend is not a plain mean. An item adored by one and rejected
    by the other must lose to an item both merely like."""
    alpha = DEFAULT_ALPHA
    lopsided = alpha * ((1.0 + 0.0) / 2) + (1 - alpha) * 0.0
    agreed = alpha * ((0.65 + 0.65) / 2) + (1 - alpha) * 0.65
    assert agreed > lopsided
    # A plain average would have called them equal, which is the failure being fixed.
    assert (1.0 + 0.0) / 2 < (0.65 + 0.65) / 2


def test_every_item_is_attributed_to_someone(service, context):
    members = [
        member("u1", "Krish", genre_affinity={"horror": 1.0}, taste_vector=[0.9, 0.1]),
        member("u2", "Amogh", genre_affinity={"romance": 1.0}, taste_vector=[0.1, 0.9]),
    ]
    result = service.blend(members, context, limit=8)
    assert result["items"]
    for entry in result["items"]:
        assert entry["owner"] in {"u1", "u2", "shared"}
        assert -1.0 <= entry["lean"] <= 1.0
        assert entry["reason"]
    counted = result["mix"]["shared"] + result["mix"]["u1"] + result["mix"]["u2"]
    assert counted == len(result["items"])


def test_representation_floor_keeps_both_members_in_the_feed(service, context):
    """One member cold-start, the other opinionated. Greedy alone would hand the
    whole feed to the opinionated one."""
    members = [
        member(
            "loud",
            "Loud",
            genre_affinity={"horror": 1.0},
            taste_vector=[1.0, 0.0],
            positive_content_ids=["c1", "c3"],
            is_cold_start=False,
        ),
        member("quiet", "Quiet"),
    ]
    result = service.blend(members, context, limit=10)
    credit = {
        "loud": result["mix"]["loud"] + 0.5 * result["mix"]["shared"],
        "quiet": result["mix"]["quiet"] + 0.5 * result["mix"]["shared"],
    }
    total = credit["loud"] + credit["quiet"]
    assert min(credit.values()) / total >= 0.30


# ---------------------------------------------------------------------------
# Candidate rule
# ---------------------------------------------------------------------------


def test_an_item_only_one_member_has_heard_stays_in(service, context):
    """"The one you loved that they have not heard" is the best thing a blend can
    surface, so only titles *both* have finished are dropped."""
    members = [
        member("u1", "Krish", interacted_content_ids=["c0", "c1"]),
        member("u2", "Amogh", interacted_content_ids=["c1", "c2"]),
    ]
    shown = {entry["content_id"] for entry in service.blend(members, context, limit=12)["items"]}
    assert "c1" not in shown          # both have heard it
    assert {"c0", "c2"} <= shown      # one each — exactly what a blend is for


def test_suppressed_duplicates_never_reach_a_blend(service, context):
    context.suppressed = {"c4"}
    members = [member("u1", "Krish"), member("u2", "Amogh")]
    shown = {entry["content_id"] for entry in service.blend(members, context, limit=12)["items"]}
    assert "c4" not in shown


def test_a_blend_needs_exactly_two_people(service, context):
    with pytest.raises(ValueError):
        service.blend([member("u1", "Solo")], context)


def test_an_empty_catalog_returns_an_empty_feed_not_an_error(service, context):
    context.catalog = {}
    result = service.blend([member("u1", "A"), member("u2", "B")], context)
    assert result["items"] == []
    assert result["candidate_pool_size"] == 0


# ---------------------------------------------------------------------------
# Taste match
# ---------------------------------------------------------------------------


def test_taste_match_is_symmetric():
    left = UserProfile(
        user_id="u1", taste_vector=[1.0, 0.2], genre_affinity={"horror": 1.0},
        positive_content_ids=["c1", "c2"],
    )
    right = UserProfile(
        user_id="u2", taste_vector=[0.9, 0.4], genre_affinity={"horror": 0.8},
        positive_content_ids=["c2", "c3"],
    )
    assert taste_match(left, right)["overall"] == taste_match(right, left)["overall"]


def test_identical_listeners_match_far_above_opposite_ones():
    same = UserProfile(
        user_id="u", taste_vector=[1.0, 0.0], genre_affinity={"horror": 1.0},
        language_affinity={"hi": 1.0}, positive_content_ids=["c1"],
    )
    opposite = UserProfile(
        user_id="v", taste_vector=[0.0, 1.0], genre_affinity={"romance": 1.0},
        language_affinity={"en": 1.0}, positive_content_ids=["c9"],
    )
    assert taste_match(same, same)["overall"] > 0.9
    assert taste_match(same, opposite)["overall"] < 0.2


def test_shared_genres_register_even_when_it_is_not_anyone_s_top_genre():
    """The profile builder min-max normalises affinity, so a genre both listeners
    enjoy sits at 0.0 for whoever ranks something else first. Cosine alone reports
    those two as having nothing in common."""
    left = UserProfile(user_id="u1", genre_affinity={"horror": 1.0, "crime-detective": 0.0})
    right = UserProfile(user_id="u2", genre_affinity={"crime-detective": 1.0, "horror": 0.0})
    assert taste_match(left, right)["genre_overlap"] > 0.0


def test_listeners_with_no_history_do_not_report_a_fake_match():
    blank = UserProfile(user_id="u1")
    assert taste_match(blank, UserProfile(user_id="u2"))["overall"] == 0.0


# ---------------------------------------------------------------------------
# Streaming — the loop split the SSE endpoint depends on
# ---------------------------------------------------------------------------


def test_stage_callback_reports_each_real_step(service, context):
    """Stages are emitted as work completes, carrying the counts actually used —
    not a progress animation."""
    seen: list[tuple[str, str, dict]] = []
    members = [member("u1", "Krish", genre_affinity={"horror": 1.0}), member("u2", "Amogh")]
    service.blend(members, context, limit=6, on_stage=lambda *args: seen.append(args))

    steps = [step for step, _, _ in seen]
    assert steps[0] == "members" and steps[-1] == "done"
    assert steps.count("score") == 2               # once per listener
    assert {"candidates", "normalise", "combine", "select"} <= set(steps)

    detail = dict(next(d for step, _, d in seen if step == "candidates"))
    assert detail["candidates"] == len(context.catalog)
    assert all("elapsed_ms" in d for _, _, d in seen)


def test_the_database_half_and_the_scoring_half_stay_separate():
    """The streaming endpoint scores on a worker thread. Mongo cannot go with it: the
    async client binds to the loop it was created on and raises `Cannot use
    AsyncMongoClient in different event loop` if a second loop touches it. So the
    awaiting methods must stay awaiting and `compose` must stay pure — collapsing
    them back together is what broke the stream once already."""
    import inspect

    from app.services.blend_service import BlendApplicationService

    assert inspect.iscoroutinefunction(BlendApplicationService.prepare)
    assert inspect.iscoroutinefunction(BlendApplicationService.mark_viewed)
    assert not inspect.iscoroutinefunction(BlendApplicationService.compose)


def test_the_stream_route_never_opens_a_second_event_loop():
    """`asyncio.run` inside the worker thread is the exact bug. Nothing in the blend
    route may create a loop."""
    from pathlib import Path

    import app.api.routes.blend as blend_route

    source = Path(blend_route.__file__).read_text(encoding="utf-8")
    assert "asyncio.run(" not in source
    assert "new_event_loop" not in source
