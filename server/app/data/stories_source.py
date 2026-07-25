"""Adapter for the platform's real `stories` collection.

This is the only module that knows the shape of the upstream catalog. It reads
`Click.stories` and maps each audio series onto our `ContentItem`. The upstream
collection is treated as **read-only** — we never write back to it.

What is real and what is derived, explicitly:

  REAL      title, description/synopsis, genre, language, author, narrator,
            episode count, average episode length, total runtime, plays, likes,
            rating, release year, premium flag, status, tags
  DERIVED   episode boundary timestamps (episodes x avgEpisodeMinutes -- the upstream
            data has counts and averages but no per-episode markers)
  ABSENT    transcripts. The catalog stores a synopsis, not a script, so the
            similarity gate's verbatim-overlap signal is automatically excluded for
            these items (see `applicable_signals`) rather than scored as a zero.
"""

from __future__ import annotations

import re
from typing import Any

from pymongo.asynchronous.collection import AsyncCollection

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.logging import get_logger
from app.data.mongo import MongoGateway
from app.domain.enums import ContentSource
from app.domain.models import Chapter, ContentItem

logger = get_logger(__name__)

#: Upstream language labels -> our codes. Hinglish is deliberately kept as its own
#: segment: on an Indian audio platform it is a distinct market with distinct
#: listeners, and folding it into `hi` would erase the exact demand signal a creator
#: needs.
LANGUAGE_MAP = {
    "hindi": "hi",
    "hinglish": "hinglish",
    "english": "en",
    "tamil": "ta",
    "telugu": "te",
    "bengali": "bn",
    "marathi": "mr",
}


def slugify_genre(genre: str) -> str:
    """'Crime & Detective' -> 'crime-detective', 'Comedy & Slice of Life' -> 'comedy-slice-of-life'."""
    cleaned = re.sub(r"[&/]+", " ", (genre or "").lower())
    cleaned = re.sub(r"[^a-z0-9\s-]", "", cleaned)
    return "-".join(cleaned.split()) or "general"


def normalise_language(language: str) -> str:
    key = (language or "").strip().lower()
    return LANGUAGE_MAP.get(key, key[:8] or "und")


def _derive_episodes(
    episode_count: int, total_seconds: int, avg_minutes: int
) -> list[Chapter]:
    """Build episode boundaries from the counts the catalog does record.

    The upstream data has `episodes` and `avgEpisodeMinutes` but no per-episode
    timestamps. Even boundaries are an approximation — real episodes vary — but they
    are derived from real metadata, and they are what makes chapter-level retention
    analysis possible at all. Flagged as derived in the summary this module returns.
    """
    count = max(1, episode_count)
    length = int(total_seconds / count) if total_seconds else max(60, avg_minutes * 60)
    return [
        Chapter(
            index=index,
            title=f"Episode {index + 1}",
            start_seconds=index * length,
            end_seconds=(index + 1) * length,
            summary="",
        )
        for index in range(count)
    ]


def story_to_content_item(document: dict[str, Any]) -> ContentItem:
    """Map one upstream story document onto a catalog item."""
    story_id = str(document.get("storyId") or document.get("_id"))
    title = str(document.get("title") or story_id).strip()
    description = str(document.get("description") or document.get("synopsis") or "").strip()
    genre = slugify_genre(str(document.get("genre") or document.get("topic") or ""))
    language = normalise_language(str(document.get("language") or ""))

    episodes = int(document.get("episodes") or document.get("episodesReleased") or 1)
    avg_minutes = int(document.get("avgEpisodeMinutes") or 0)
    total_minutes = int(document.get("totalDurationMinutes") or (episodes * max(avg_minutes, 1)))
    duration_seconds = max(60, total_minutes * 60)

    tags = [str(tag).strip().lower() for tag in (document.get("tags") or []) if str(tag).strip()]
    extra_tags = [
        value
        for value in (
            str(document.get("status") or "").lower(),
            str(document.get("ageRating") or "").lower(),
            "premium" if document.get("isPremium") else "free",
        )
        if value
    ]

    return ContentItem(
        content_id=story_id,
        title=title,
        # No script exists upstream; the synopsis is the richest text we have.
        transcript=description,
        description=description,
        creator_id=str(document.get("author") or "unknown"),
        language=language,
        genres=[genre],
        tags=sorted(set(tags + extra_tags))[:24],
        duration_seconds=duration_seconds,
        chapters=_derive_episodes(episodes, duration_seconds, avg_minutes),
        source=ContentSource.PLATFORM,
        is_synthetic=False,
        published_at=document.get("createdAt") or utcnow(),
        created_at=document.get("updatedAt") or document.get("createdAt") or utcnow(),
        # Real platform aggregates, carried through so the simulator and the demand
        # engine can anchor on measured popularity instead of inventing it.
        popularity=_popularity(document),
    )


def _popularity(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "plays": int(document.get("plays") or 0),
        "likes": int(document.get("likes") or 0),
        "rating": float(document.get("rating") or 0.0),
        "episodes": int(document.get("episodes") or 0),
        "episodes_released": int(document.get("episodesReleased") or 0),
        "status": str(document.get("status") or ""),
        "is_premium": bool(document.get("isPremium")),
        "release_year": int(document.get("releaseYear") or 0),
        "narrator": str(document.get("narrator") or ""),
        "age_rating": str(document.get("ageRating") or ""),
        "source": "platform_catalog",
    }


class StoriesSource:
    """Read-only access to the upstream catalog collection."""

    def __init__(self, gateway: MongoGateway, settings: Settings) -> None:
        self._gateway = gateway
        self._settings = settings

    @property
    def collection(self) -> AsyncCollection:
        return self._gateway.database[self._settings.stories_collection]

    async def available(self) -> bool:
        names = await self._gateway.database.list_collection_names()
        return self._settings.stories_collection in names

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def load(self, limit: int = 0) -> list[ContentItem]:
        cursor = self.collection.find({})
        if limit:
            cursor = cursor.limit(limit)
        items: list[ContentItem] = []
        skipped = 0
        async for document in cursor:
            try:
                items.append(story_to_content_item(document))
            except Exception:  # noqa: BLE001 - one malformed row must not kill the import
                skipped += 1
                logger.exception("Skipping unmappable story %s", document.get("_id"))
        if skipped:
            logger.warning("Skipped %d unmappable stories", skipped)
        return items

    @staticmethod
    def summarise(items: list[ContentItem]) -> dict[str, Any]:
        from collections import Counter

        return {
            "stories": len(items),
            "genres": dict(Counter(item.primary_genre for item in items).most_common()),
            "languages": dict(Counter(item.language for item in items).most_common()),
            "creators": len({item.creator_id for item in items}),
            "total_episodes": sum(len(item.chapters) for item in items),
            "total_plays": sum(item.popularity.get("plays", 0) for item in items),
            "fields_real": [
                "title", "description", "genre", "language", "author", "narrator",
                "episodes", "avgEpisodeMinutes", "totalDurationMinutes",
                "plays", "likes", "rating", "releaseYear", "status", "isPremium", "tags",
            ],
            "fields_derived": ["episode boundary timestamps (episodes x average length)"],
            "fields_absent": ["transcripts — the catalog stores a synopsis, not a script"],
        }
