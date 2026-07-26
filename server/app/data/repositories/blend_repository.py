"""Blend persistence. A blend is a pair of accounts, nothing more."""

from __future__ import annotations

from app.data.mongo import Collections
from app.data.repositories.base import BaseRepository
from app.domain.models import Blend


class BlendRepository(BaseRepository[Blend]):
    collection_name = Collections.BLENDS
    model_type = Blend
    key_field = "blend_id"

    async def between(self, left_user_id: str, right_user_id: str) -> Blend | None:
        """The existing blend for this pair, in either direction.

        Membership is stored sorted, so one query covers both orderings and the
        "A adds B" / "B adds A" cases cannot produce two separate blends.
        """
        found = await self.find(
            {"member_ids": sorted([left_user_id, right_user_id])}, limit=1
        )
        return found[0] if found else None

    async def for_member(self, user_id: str, limit: int = 25) -> list[Blend]:
        return await self.find(
            {"member_ids": user_id}, limit=limit, sort=[("created_at", -1)]
        )

    async def delete(self, blend_id: str) -> bool:
        result = await self.collection.delete_one({"blend_id": blend_id})
        return result.deleted_count > 0
