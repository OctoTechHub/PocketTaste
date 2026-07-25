"""The real-catalog path: upstream story mapping, provenance, and GOAT wiring.

No database and no network — the upstream document shape is exercised directly.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.enums import Provenance
from app.domain.provenance import notice, resolve_provenance
from app.data.stories_source import (
    StoriesSource,
    normalise_language,
    slugify_genre,
    story_to_content_item,
)

#: A document in the exact shape of the platform's `stories` collection.
STORY_DOC = {
    "_id": "aadhi-raat-ka-mehmaan",
    "storyId": "aadhi-raat-ka-mehmaan",
    "title": "Aadhi Raat Ka Mehmaan",
    "genre": "Crime & Detective",
    "topic": "Horror",
    "description": "Ek sunsan haveli mein har raat theek 3 baje darwaza khatakta hai.",
    "synopsis": "Ek sunsan haveli mein har raat theek 3 baje darwaza khatakta hai.",
    "author": "Neha Sharma",
    "narrator": "Sooraj Thapa",
    "language": "Hinglish",
    "type": "audio_series",
    "episodes": 10,
    "episodesReleased": 10,
    "avgEpisodeMinutes": 7,
    "totalDurationMinutes": 70,
    "plays": 5881154,
    "likes": 582234,
    "rating": 4.4,
    "ageRating": "18+",
    "status": "Completed",
    "isPremium": True,
    "releaseYear": 2023,
    "tags": ["horror", "scary"],
    "createdAt": datetime(2026, 7, 25, tzinfo=timezone.utc),
}


# ---------------------------------------------------------------------------
# Genre / language normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Crime & Detective", "crime-detective"),
        ("Mythology & Fantasy", "mythology-fantasy"),
        ("Comedy & Slice of Life", "comedy-slice-of-life"),
        ("Revenge Drama", "revenge-drama"),
        ("Sci-Fi", "sci-fi"),
        ("Horror", "horror"),
        ("", "general"),
    ],
)
def test_genres_slugify_predictably(raw, expected):
    assert slugify_genre(raw) == expected


def test_hinglish_stays_its_own_language():
    """Folding Hinglish into Hindi would erase a distinct market segment."""
    assert normalise_language("Hinglish") == "hinglish"
    assert normalise_language("Hindi") == "hi"
    assert normalise_language("English") == "en"
    assert normalise_language("Hinglish") != normalise_language("Hindi")


# ---------------------------------------------------------------------------
# Document mapping
# ---------------------------------------------------------------------------


def test_upstream_story_maps_onto_a_catalog_item():
    item = story_to_content_item(STORY_DOC)
    assert item.content_id == "aadhi-raat-ka-mehmaan"
    assert item.title == "Aadhi Raat Ka Mehmaan"
    assert item.genres == ["crime-detective"]
    assert item.language == "hinglish"
    assert item.creator_id == "Neha Sharma"
    assert item.duration_seconds == 70 * 60
    assert item.is_synthetic is False


def test_episode_markers_are_derived_from_the_real_counts():
    """The catalog has episode counts and an average length but no per-episode
    timestamps; boundaries are derived so chapter-level retention is possible."""
    item = story_to_content_item(STORY_DOC)
    assert len(item.chapters) == 10
    assert item.chapters[0].start_seconds == 0
    assert item.chapters[-1].end_seconds == item.duration_seconds
    # Contiguous, no gaps or overlaps.
    for previous, current in zip(item.chapters, item.chapters[1:]):
        assert previous.end_seconds == current.start_seconds


def test_real_aggregates_are_carried_through_untouched():
    popularity = story_to_content_item(STORY_DOC).popularity
    assert popularity["plays"] == 5881154
    assert popularity["likes"] == 582234
    assert popularity["rating"] == 4.4
    assert popularity["narrator"] == "Sooraj Thapa"
    assert popularity["source"] == "platform_catalog"


def test_mapping_survives_a_sparse_document():
    item = story_to_content_item({"storyId": "x", "title": "X", "description": "d"})
    assert item.content_id == "x"
    assert item.duration_seconds >= 60
    assert len(item.chapters) >= 1


def test_summary_declares_what_is_real_derived_and_absent():
    summary = StoriesSource.summarise([story_to_content_item(STORY_DOC)])
    assert summary["stories"] == 1
    assert summary["total_plays"] == 5881154
    assert any("episode boundary" in field for field in summary["fields_derived"])
    assert any("transcript" in field for field in summary["fields_absent"])


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("catalog_total", "catalog_synthetic", "events_total", "events_synthetic", "expected"),
    [
        (10, 0, 100, 0, Provenance.REAL),
        (10, 0, 0, 0, Provenance.REAL),
        (10, 0, 100, 100, Provenance.SIMULATED_FROM_REAL_CATALOG),
        (10, 10, 100, 100, Provenance.SYNTHETIC_SIMULATION),
        (10, 5, 100, 100, Provenance.MIXED),
        (10, 0, 100, 40, Provenance.MIXED),
        (0, 0, 0, 0, Provenance.REAL),
    ],
)
def test_provenance_needs_both_catalog_and_event_realness(
    catalog_total, catalog_synthetic, events_total, events_synthetic, expected
):
    assert (
        resolve_provenance(
            catalog_total=catalog_total,
            catalog_synthetic=catalog_synthetic,
            events_total=events_total,
            events_synthetic=events_synthetic,
        )
        is expected
    )


def test_every_provenance_state_has_a_disclosure():
    for state in Provenance:
        text = notice(state)
        assert len(text) > 40
    assert "REAL" in notice(Provenance.SIMULATED_FROM_REAL_CATALOG)
    assert "SIMULATED" in notice(Provenance.SIMULATED_FROM_REAL_CATALOG)
    assert "SYNTHETIC" in notice(Provenance.SYNTHETIC_SIMULATION)


# ---------------------------------------------------------------------------
# GOAT integration
# ---------------------------------------------------------------------------


def test_goat_package_is_installed_and_reports_itself():
    from app.services.goat_agent import GOAT_AVAILABLE, GoatStorytellingEngine
    from app.core.config import Settings

    assert GOAT_AVAILABLE, "the upstream GOAT package must be installed"

    described = GoatStorytellingEngine(Settings(_env_file=None, OPENAI_KEY="")).describe()
    assert described["package"] == "goat_storytelling_agent"
    assert "GOAT-AI-lab" in described["upstream"]
    assert described["installed"] is True
    # No API key configured, so it must report itself unavailable rather than pretend.
    assert described["available"] is False
    assert described["stages"][:2] == ["init_book_spec", "create_plot_chapters"]


def test_goat_subclass_overrides_only_the_transport():
    """The value of the integration is that GOAT's own prompts and parsers run."""
    from goat_storytelling_agent.storytelling_agent import StoryAgent

    from app.services.goat_agent import OpenAIBackedStoryAgent

    assert issubclass(OpenAIBackedStoryAgent, StoryAgent)
    # query_chat is ours; everything else is inherited from upstream.
    assert "query_chat" in OpenAIBackedStoryAgent.__dict__
    for inherited in (
        "init_book_spec",
        "create_plot_chapters",
        "enhance_plot_chapters",
        "split_chapters_into_scenes",
        "parse_book_spec",
    ):
        assert inherited not in OpenAIBackedStoryAgent.__dict__
        assert hasattr(OpenAIBackedStoryAgent, inherited)


def test_goat_act_major_plan_flattens_to_numbered_episodes():
    from app.services.goat_agent import flatten_chapters

    plan = [
        {
            "act_descr": "Act 1: setup",
            "chapters": [
                "A Silent Vigil**\n\nAnjali starts her shift and notices something wrong.",
                "The Confessions**\n\nShe reviews the footage again.",
            ],
        },
        {"act_descr": "Act 2: escalation", "chapters": ["The Web Tightens**\n\nEvidence mounts."]},
    ]
    chapters = flatten_chapters(plan)

    assert [chapter["index"] for chapter in chapters] == [1, 2, 3]
    assert [chapter["act"] for chapter in chapters] == [1, 1, 2]
    # Markdown emphasis stripped, and the title is the first line — not the first
    # sentence, which would cut into the body.
    assert chapters[0]["title"] == "A Silent Vigil"
    assert "Anjali starts her shift" in chapters[0]["beat"]
    assert "**" not in chapters[0]["title"]


def test_flatten_handles_an_unsplit_paragraph():
    from app.services.goat_agent import flatten_chapters

    chapters = flatten_chapters([{"act_descr": "Act 1", "chapters": ["Short title. Then the body runs on."]}])
    assert chapters[0]["title"] == "Short title"
    assert "body runs on" in chapters[0]["beat"]


def test_flatten_of_an_empty_plan_is_empty():
    from app.services.goat_agent import flatten_chapters

    assert flatten_chapters([]) == []
    assert flatten_chapters(None) == []
