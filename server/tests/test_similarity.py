"""The plagiarism gate. Runs fully offline: hash embeddings, heuristic labels, no LLM."""

from __future__ import annotations

import pytest
from conftest import make_item

from app.domain.enums import DuplicateKind, RiskLevel
from app.domain.models import SimilaritySignals
from app.services.content_intelligence import ContentIntelligenceService, normalise_title
from app.services.embeddings import EmbeddingService
from app.services.llm import LlmService
from app.services.similarity import (
    SimilarityCandidate,
    SimilarityService,
    applicable_signals,
)

ORIGINAL_TRANSCRIPT = (
    "Arjun wakes inside a collapsed dungeon after a failed raid. A hidden system grants "
    "him quests, levels and a chance to protect his sister from the monsters pouring out "
    "of the gates. Each rank he gains costs him a memory he cannot name. By the ninth "
    "gate he no longer remembers why he started climbing."
) * 4


@pytest.fixture
def service(settings):
    embeddings = EmbeddingService(settings)
    llm = LlmService(settings)
    return SimilarityService(settings, ContentIntelligenceService(settings, embeddings, llm), llm)


@pytest.fixture
async def profiled(settings):
    """Build a small catalog with real (hash-backed) profiles."""
    embeddings = EmbeddingService(settings)
    intelligence = ContentIntelligenceService(settings, embeddings, LlmService(settings))
    catalog = [
        make_item("orig", title="Ashen Throne", transcript=ORIGINAL_TRANSCRIPT, genres=["fantasy"]),
        make_item(
            "other",
            title="Monsoon Vow",
            description="A widowed baker returns to her home town to sell a shop.",
            transcript="Meera returns to Kolhapur to sell the bakery her mother left her. "
            "The man behind the counter is the one she walked away from." * 6,
            genres=["romance"],
            language="hi",
        ),
    ]
    profiles = {item.content_id: await intelligence.analyse(item, use_llm=False) for item in catalog}
    return catalog, profiles


# ---------------------------------------------------------------------------
# Title normalisation — the "Solo Leveling Season 3" case from the brief
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Solo Leveling",
        "Solo Leveling Season 3",
        "Solo Leveling: The End",
        "Solo Leveling Part II",
        "SOLO LEVELING (Final)",
        "Solo Leveling - Hindi Version",
        "Solo Leveling Episode 12",
    ],
)
def test_series_markers_normalise_to_one_key(title):
    assert normalise_title(title) == "solo leveling"


def test_distinct_titles_keep_distinct_keys():
    assert normalise_title("Ashen Throne") != normalise_title("Crimson Throne")


# ---------------------------------------------------------------------------
# Signal applicability
# ---------------------------------------------------------------------------


def test_short_premise_excludes_signals_that_cannot_be_measured():
    premise = make_item("draft", transcript="A hunter finds a system.", chapters=0)
    signals = applicable_signals(premise)
    assert "lexical_shingle" not in signals    # too little text to shingle
    assert "chapter_structure" not in signals  # no chapter markers
    assert {"narrative_arc", "semantic", "title", "description"} <= signals


def test_a_logline_length_story_can_still_be_checked_for_verbatim_copying():
    """The live catalog stores loglines, median 98 characters. The floor used to be 60
    tokens, which switched the copy-paste detector off for nearly every real upload."""
    logline = make_item(
        "draft",
        transcript="Ek unknown number se message aata hai: 'main tumhare theek peeche "
        "khada hoon.' Rahul peeche mudta hai aur usi pal phone ki battery 0% ho jaati hai.",
        chapters=0,
    )
    assert "lexical_shingle" in applicable_signals(logline)


def test_full_upload_uses_every_signal():
    full = make_item("draft", transcript=ORIGINAL_TRANSCRIPT, chapters=6)
    assert applicable_signals(full) == {
        "narrative_arc",
        "semantic",
        "lexical_shingle",
        "title",
        "description",
        "chapter_structure",
    }


# ---------------------------------------------------------------------------
# End-to-end verdicts
# ---------------------------------------------------------------------------


async def test_verbatim_reupload_under_a_new_title_is_blocked(service, profiled):
    catalog, profiles = profiled
    report = await service.screen(
        SimilarityCandidate(
            title="A Completely Unrelated Name",
            description="A totally different sounding blurb.",
            transcript=ORIGINAL_TRANSCRIPT,
            genres=["fantasy"],
        ),
        catalog,
        profiles,
        use_llm=False,
    )
    assert report.risk is RiskLevel.BLOCK
    assert report.duplicate_kind is DuplicateKind.EXACT_DUPLICATE
    assert report.matches[0].content_id == "orig"
    assert report.matches[0].signals.lexical_shingle > 0.9


async def test_identical_normalised_title_forces_at_least_review(service, profiled):
    """Titles collide after stripping 'Season 4' even though the draft is only a premise."""
    catalog, profiles = profiled
    report = await service.screen(
        SimilarityCandidate(
            title="Ashen Throne Season 4",
            description="Something quite different about a baker in a coastal town.",
            transcript="A baker in a coastal town.",
            genres=["romance"],
        ),
        catalog,
        profiles,
        use_llm=False,
    )
    assert report.risk in (RiskLevel.REVIEW, RiskLevel.BLOCK)
    assert any(match.signals.title >= 1.0 for match in report.matches)


async def test_unrelated_original_story_is_cleared(service, profiled):
    catalog, profiles = profiled
    report = await service.screen(
        SimilarityCandidate(
            title="The Salt Ledger",
            description="A blind tax clerk audits a salt monopoly in 1890s Bombay.",
            transcript=(
                "The clerk reads the ledger by the weight of its ink. Every column names a "
                "debtor who has not yet been born, and the inspector who hired him has been "
                "dead two years according to the register he signs each morning."
            )
            * 4,
            genres=["thriller"],
        ),
        catalog,
        profiles,
        use_llm=False,
    )
    assert report.risk is RiskLevel.CLEAR
    assert report.duplicate_kind is DuplicateKind.NONE
    assert report.originality_score > 0.5


async def test_report_is_self_describing(service, profiled):
    catalog, profiles = profiled
    report = await service.screen(
        SimilarityCandidate(title="Anything", description="A blurb.", transcript="Some words here."),
        catalog,
        profiles,
        use_llm=False,
    )
    assert report.weights and report.thresholds and report.applied_signals
    assert report.explanation
    assert "not a legal plagiarism ruling" in report.disclaimer
    assert report.originality_score == round(1.0 - report.top_score, 4)


async def test_excluded_content_id_is_not_compared_against_itself(service, profiled):
    catalog, profiles = profiled
    report = await service.screen(
        SimilarityCandidate(
            title="Ashen Throne", description="Same story.", transcript=ORIGINAL_TRANSCRIPT
        ),
        catalog,
        profiles,
        exclude_content_id="orig",
        use_llm=False,
    )
    assert all(match.content_id != "orig" for match in report.matches)


async def test_empty_catalog_yields_no_finding_rather_than_a_false_positive(service):
    report = await service.screen(
        SimilarityCandidate(title="Anything", description="A blurb.", transcript="Words."),
        [],
        {},
        use_llm=False,
    )
    assert report.risk is RiskLevel.CLEAR
    assert report.matches == []
    assert report.originality_score == 1.0


# ---------------------------------------------------------------------------
# Reworded copies - the case the thresholds were retuned for
# ---------------------------------------------------------------------------


async def test_a_strong_skeleton_match_alone_triggers_review(service, profiled):
    """The Solo Leveling case: same story, new title, every word rewritten.

    Verbatim overlap is ~0, the title does not match, and there are no chapters. Only
    the arc signal fires. If the blend is allowed to average those zeros in, the copy
    passes as clear -- which is exactly what happened before this rule existed.
    """
    from app.services.similarity import _ARC_ALONE_REVIEW
    from app.domain.models import SimilarityMatch, SimilaritySignals

    strong_arc = SimilarityMatch(
        content_id="orig", title="Ashen Throne", creator_id="c", language="en",
        combined_score=0.55,                       # below the 0.72 review threshold
        signals=SimilaritySignals(narrative_arc=_ARC_ALONE_REVIEW + 0.02, semantic=0.60),
    )
    assert service._verdict(0.55, DuplicateKind.NONE, None, strong_arc) is RiskLevel.REVIEW


def test_a_weak_skeleton_match_stays_clear(service):
    """Two unrelated stories in one genre must not trip the same rule."""
    from app.domain.models import SimilarityMatch, SimilaritySignals

    typical = SimilarityMatch(
        content_id="other", title="Iron Realm", creator_id="c", language="en",
        combined_score=0.55,
        signals=SimilaritySignals(narrative_arc=0.72, semantic=0.70),   # the real-catalog ceiling
    )
    assert service._verdict(0.55, DuplicateKind.NONE, None, typical) is RiskLevel.CLEAR


def test_arc_threshold_sits_above_the_measured_genuine_ceiling():
    """Calibration guard. Across 4,950 real distinct pairs the arc peaks at 0.726, and
    a reworded re-upload measures 0.85. Both thresholds must sit in that gap."""
    from app.services.similarity import _ARC_ALONE_REVIEW, _NEAR_ARC_THRESHOLD

    measured_genuine_ceiling = 0.726
    measured_reworded_copy = 0.85
    for threshold in (_ARC_ALONE_REVIEW, _NEAR_ARC_THRESHOLD):
        assert measured_genuine_ceiling < threshold < measured_reworded_copy


# ---------------------------------------------------------------------------
# Episode ranges - found by running the gate over real YouTube re-uploads
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Yakshini 701 to 800 | Pocket FM", (701, 800)),
        ("Lust System In Solo Leveling Episode 21-50", (21, 50)),
        ("Yakshini 101 se 200 tak", (101, 200)),
        ("Mysterious Doctor Episode 1 TO 50 Complete", (1, 50)),
        ("Solo Leveling Season 3", None),
        ("Ashen Throne: The End", None),
    ],
)
def test_episode_ranges_are_read_from_the_title(title, expected):
    from app.services.content_intelligence import episode_range

    assert episode_range(title) == expected


def test_consecutive_parts_are_not_duplicates(service):
    """Real case from the live catalog: "Yakshini 701 to 800" and "Yakshini 801 to
    900" normalise to the same key because digits are stripped, so the title signal
    read 1.0 and called them a re-upload. They are consecutive parts of one series —
    normal publishing."""
    from app.services.content_intelligence import normalise_title

    a, b = "Yakshini 701 to 800 | Pocket FM", "Yakshini 801 to 900 | Pocket FM"
    assert normalise_title(a) == normalise_title(b)          # the trap

    tokens = set()
    assert service._title_signal(normalise_title(a), tokens, b, a) < 0.5
    assert service._classify(SimilaritySignals(narrative_arc=0.97, semantic=0.97),
                             normalise_title(a), b, a) is DuplicateKind.NONE


def test_overlapping_ranges_are_still_duplicates(service):
    """Re-uploading 1-100 as 50-150 is republishing the same episodes."""
    from app.services.content_intelligence import normalise_title

    a, b = "Yakshini 1 to 100", "Yakshini 50 to 150"
    assert service._title_signal(normalise_title(a), set(), b, a) == 1.0


# ---------------------------------------------------------------------------
# Verbatim overlap - found by re-uploading a real catalog story under a new title
# ---------------------------------------------------------------------------


def test_a_short_text_copied_into_a_long_one_is_not_hidden_by_the_union():
    """Jaccard divides by the union, so a logline lifted word for word into a long
    script scores low purely because the long side adds unshared shingles. Containment
    asks the question a re-upload check is actually posing."""
    from app.services.vectors import containment, jaccard, shingles, verbatim_overlap

    short = shingles(
        "Ek unknown number se message aata hai main tumhare theek peeche khada hoon "
        "Rahul peeche mudta hai aur usi pal phone ki battery zero percent ho jaati hai"
    )
    long = short | shingles(
        "Uske baad woh apne dost ko phone karta hai lekin line par koi aur hai jo uski "
        "aawaz mein baat karta hai aur poori raat wahi ek sawaal dohraata rehta hai"
    )
    assert jaccard(short, long) < 0.6          # the union hides it
    assert containment(short, long) == 1.0     # every shingle of the copy is present
    assert verbatim_overlap(short, long) == 1.0


def test_containment_ignores_texts_too_small_to_judge():
    """Three shared stock phrases must not read as a total copy."""
    from app.services.vectors import containment, shingles

    assert containment(shingles("he walked into the dark room"), shingles("x " * 400)) == 0.0


async def test_an_identical_story_under_a_new_title_and_blurb_is_blocked(service, profiled):
    """The brief's case: same content inside, different name and description."""
    catalog, profiles = profiled
    original = catalog[0]
    report = await service.screen(
        SimilarityCandidate(
            title="Peeche Mat Dekhna - Season 2",
            description="Ek naye mod par shuru hone wali sabse darawni raat.",
            transcript=original.transcript,
            genres=["horror"],
        ),
        catalog,
        profiles,
        use_llm=False,
    )
    assert report.risk is RiskLevel.BLOCK
    assert report.duplicate_kind is DuplicateKind.EXACT_DUPLICATE
    assert report.matches[0].content_id == original.content_id
    assert report.matches[0].signals.lexical_shingle == 1.0


def test_a_season_marker_still_collides(service):
    """No range declared, so the season rule must keep working."""
    from app.services.content_intelligence import normalise_title

    a, b = "Solo Leveling Season 3", "Solo Leveling"
    assert service._title_signal(normalise_title(a), set(), b, a) == 1.0
