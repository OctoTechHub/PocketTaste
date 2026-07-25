"""Repositories for everything the agents derive: profiles, features, user state."""

from __future__ import annotations

from app.data.mongo import Collections
from app.data.repositories.base import BaseRepository
from app.domain.models import ContentFeatures, ContentProfile, UserProfile


class ContentProfileRepository(BaseRepository[ContentProfile]):
    collection_name = Collections.PROFILES
    model_type = ContentProfile
    key_field = "content_id"

    async def get_many(self, content_ids: list[str]) -> dict[str, ContentProfile]:
        if not content_ids:
            return {}
        profiles = await self.find({"content_id": {"$in": content_ids}})
        return {profile.content_id: profile for profile in profiles}

    async def all_by_id(self) -> dict[str, ContentProfile]:
        return {profile.content_id: profile for profile in await self.list_all()}

    async def ids_with_embeddings(self) -> set[str]:
        cursor = self.collection.find({"embedding.0": {"$exists": True}}, {"content_id": 1})
        return {doc["content_id"] async for doc in cursor}

    async def cluster_members(self, cluster_id: str) -> list[ContentProfile]:
        return await self.find({"cluster_id": cluster_id})


class ContentFeaturesRepository(BaseRepository[ContentFeatures]):
    collection_name = Collections.FEATURES
    model_type = ContentFeatures
    key_field = "content_id"

    async def get_many(self, content_ids: list[str]) -> dict[str, ContentFeatures]:
        if not content_ids:
            return {}
        rows = await self.find({"content_id": {"$in": content_ids}})
        return {row.content_id: row for row in rows}

    async def all_by_id(self) -> dict[str, ContentFeatures]:
        return {row.content_id: row for row in await self.list_all()}


class UserProfileRepository(BaseRepository[UserProfile]):
    collection_name = Collections.USERS
    model_type = UserProfile
    key_field = "user_id"

    async def sample(self, limit: int) -> list[UserProfile]:
        return await self.find({"is_cold_start": False}, limit=limit, sort=[("events_observed", -1)])
