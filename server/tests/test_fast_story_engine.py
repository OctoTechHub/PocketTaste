"""The fast outlining engine. Structure only — no network."""

from __future__ import annotations

import pytest

from app.services.fast_story_engine import FastStoryEngine
from app.services.llm import LlmService


@pytest.fixture
def engine(settings) -> FastStoryEngine:
    return FastStoryEngine(settings, LlmService(settings))


def test_chapter_indices_are_assigned_by_position_not_by_the_model(engine):
    """Models return duplicated, one-based or missing indices often enough that
    trusting them puts two chapters in the same slot."""
    raw = [
        {"index": 7, "act": 1, "title": "A", "beat": "b", "hook": "h"},
        {"index": 7, "act": 2, "title": "B", "beat": "b", "hook": "h"},
        {"act": 3, "title": "C", "beat": "b", "hook": "h"},
    ]
    chapters = engine._clean_chapters(raw, target=3)
    assert [c["index"] for c in chapters] == [0, 1, 2]
    assert [c["act"] for c in chapters] == [1, 2, 3]


def test_more_chapters_than_asked_for_are_dropped(engine):
    raw = [{"title": f"C{i}", "beat": "b", "hook": "h"} for i in range(20)]
    assert len(engine._clean_chapters(raw, target=6)) == 6


def test_a_missing_title_still_yields_a_usable_chapter(engine):
    chapters = engine._clean_chapters([{"beat": "something happens"}], target=1)
    assert chapters[0]["title"] == "Chapter 1"
    assert chapters[0]["beat"] == "something happens"


def test_a_non_list_payload_is_not_a_crash(engine):
    assert engine._clean_chapters(None, target=4) == []
    assert engine._clean_chapters({"chapters": []}, target=4) == []
    assert engine._clean_chapters(["not a dict"], target=4) == []


def test_an_out_of_range_act_is_replaced_rather_than_trusted(engine):
    chapters = engine._clean_chapters(
        [{"act": 99, "title": "A", "beat": "b", "hook": "h"}], target=1
    )
    assert 1 <= chapters[0]["act"] <= 3


def test_the_engine_reports_what_it_gives_up_against_goat(engine):
    described = engine.describe()
    assert "enhance_plot_chapters" in " ".join(described["drops_from_goat"])
    assert "three-act structure" in described["keeps_from_goat"]
