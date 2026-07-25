"""Shared fixtures. These tests are pure — no MongoDB, no network, no API keys."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.clock import days_ago  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.domain.enums import EventType  # noqa: E402
from app.domain.models import ActivityEvent, Chapter, ContentItem  # noqa: E402


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Offline settings: no Mongo URI, no API key, so every service uses its fallback."""
    return Settings(_env_file=None, DB_URL="", OPENAI_KEY="", OPENAI_API_KEY="", SARVAM_API_KEY="")


def make_item(
    content_id: str,
    *,
    title: str = "A Story",
    description: str = "A description long enough to be useful for tests.",
    transcript: str = "",
    language: str = "en",
    genres: list[str] | None = None,
    duration: int = 3600,
    chapters: int = 6,
    published_days_ago: float = 10.0,
) -> ContentItem:
    length = duration // max(chapters, 1)
    return ContentItem(
        content_id=content_id,
        title=title,
        description=description,
        transcript=transcript or f"{description} " * 12,
        creator_id="creator_test",
        language=language,
        genres=genres or ["fantasy"],
        duration_seconds=duration,
        chapters=[
            Chapter(
                index=index,
                title=f"Chapter {index + 1}",
                start_seconds=index * length,
                end_seconds=(index + 1) * length,
            )
            for index in range(chapters)
        ],
        published_at=days_ago(published_days_ago),
    )


def make_event(
    user_id: str,
    content_id: str,
    event_type: EventType,
    *,
    position: int = 0,
    session: str = "sess_1",
    chapter: int | None = None,
    days: float = 1.0,
    synthetic: bool = True,
) -> ActivityEvent:
    return ActivityEvent(
        event_id=f"evt_{user_id}_{content_id}_{event_type.value}_{position}_{session}",
        user_id=user_id,
        content_id=content_id,
        session_id=session,
        event_type=event_type,
        position_seconds=position,
        chapter_index=chapter,
        session_seconds=300,
        is_synthetic=synthetic,
        occurred_at=days_ago(days),
    )


@pytest.fixture
def catalog() -> list[ContentItem]:
    return [
        make_item("c1", title="Ashen Throne", genres=["fantasy"], language="en"),
        make_item("c2", title="Silent Verdict", genres=["thriller"], language="en"),
        make_item("c3", title="Monsoon Vow", genres=["romance"], language="hi"),
    ]
