"""The plagiarism gate. Runs fully offline: hash embeddings, heuristic labels, no LLM."""

from __future__ import annotations

import pytest
from conftest import make_item

from app.domain.enums import DuplicateKind, RiskLevel
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
