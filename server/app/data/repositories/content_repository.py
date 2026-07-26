"""Catalog persistence."""

from __future__ import annotations

from app.data.mongo import Collections
from app.data.repositories.base import BaseRepository
from app.domain.models import ContentItem

#: Transcripts and narrated audio are large; most read paths never need them.
LIGHT_PROJECTION = {"transcript": 0, "audio_base64": 0}


class ContentRepository(BaseRepository[ContentItem]):
    collection_name = Collections.CONTENT
    model_type = ContentItem
    key_field = "content_id"

    async def list_catalog(
        self,
        *,
        language: str | None = None,
        genre: str | None = None,
        creator_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        with_transcript: bool = False,
    ) -> list[ContentItem]:
        query: dict = {}
        if language:
            query["language"] = language
        if genre:
            query["genres"] = genre
        if creator_id:
            query["creator_id"] = creator_id
        projection = None if with_transcript else LIGHT_PROJECTION
        # Mongo sorts full documents in memory *before* applying the projection, so
        # a large narrated audio_base64 field can blow the 32MB sort limit even
        # though we don't return it. Spill to disk instead of aborting.
        cursor = (
            self.collection.find(query, projection)
            .sort("published_at", -1)
            .allow_disk_use(True)
            .skip(offset)
            .limit(limit)
        )
        return [ContentItem.model_validate(self._clean(doc) | {"transcript": doc.get("transcript", "")})
                async for doc in cursor]

    async def get_many(self, content_ids: list[str], *, with_transcript: bool = False) -> list[ContentItem]:
        if not content_ids:
            return []
        projection = None if with_transcript else LIGHT_PROJECTION
        cursor = self.collection.find({"content_id": {"$in": content_ids}}, projection)
        return [ContentItem.model_validate(self._clean(doc) | {"transcript": doc.get("transcript", "")})
                async for doc in cursor]

    async def iter_all(self, *, with_transcript: bool = True) -> list[ContentItem]:
        projection = None if with_transcript else LIGHT_PROJECTION
        cursor = self.collection.find({}, projection)
        return [ContentItem.model_validate(self._clean(doc) | {"transcript": doc.get("transcript", "")})
                async for doc in cursor]

    async def distinct_languages(self) -> list[str]:
        return sorted(await self.collection.distinct("language"))

    async def distinct_genres(self) -> list[str]:
        return sorted(await self.collection.distinct("genres"))
