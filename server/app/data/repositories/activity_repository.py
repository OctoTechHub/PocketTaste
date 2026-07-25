"""Activity-event persistence and the aggregations the feature builder needs."""

from __future__ import annotations

from datetime import datetime

from pymongo.errors import BulkWriteError

from app.data.mongo import Collections
from app.data.repositories.base import BaseRepository, to_document
from app.domain.enums import EventType
from app.domain.models import ActivityEvent


class ActivityRepository(BaseRepository[ActivityEvent]):
    collection_name = Collections.ACTIVITY
    model_type = ActivityEvent
    key_field = "event_id"

    async def insert_many(self, events: list[ActivityEvent]) -> int:
        """Append-only insert. Duplicate event_ids are ignored rather than failing the batch."""
        if not events:
            return 0
        try:
            result = await self.collection.insert_many(
                [to_document(event) for event in events], ordered=False
            )
            return len(result.inserted_ids)
        except BulkWriteError as exc:
            written = exc.details.get("nInserted", 0)
            return written

    async def for_content(self, content_id: str) -> list[ActivityEvent]:
        return await self.find({"content_id": content_id}, sort=[("occurred_at", 1)])

    async def for_user(self, user_id: str, limit: int = 2000) -> list[ActivityEvent]:
        return await self.find({"user_id": user_id}, limit=limit, sort=[("occurred_at", 1)])

    async def stream_all(self, since: datetime | None = None, batch_size: int = 5000) -> list[ActivityEvent]:
        query: dict = {}
        if since:
            query["occurred_at"] = {"$gte": since}
        cursor = self.collection.find(query).sort("occurred_at", 1).batch_size(batch_size)
        return [ActivityEvent.model_validate(self._clean(doc)) async for doc in cursor]

    async def search_events(self, limit: int = 5000) -> list[ActivityEvent]:
        return await self.find({"event_type": EventType.SEARCH.value}, limit=limit)

    async def unique_user_count(self) -> int:
        return len(await self.collection.distinct("user_id"))

    async def co_occurrence_pairs(self, positive_events: list[str]) -> list[dict]:
        """Item-item co-occurrence: users who positively engaged with A also engaged with B.

        Computed in the database so the API process never holds the full event log.
        """
        pipeline = [
            {"$match": {"event_type": {"$in": positive_events}, "content_id": {"$ne": None}}},
            {"$group": {"_id": "$user_id", "items": {"$addToSet": "$content_id"}}},
            {"$match": {"items.1": {"$exists": True}}},   # at least 2 distinct items
            {"$project": {"items": 1, "count": {"$size": "$items"}}},
            {"$match": {"count": {"$lte": 60}}},          # ignore pathological power users
        ]
        # pymongo's async driver returns a coroutine from aggregate(); the cursor
        # only exists once it is awaited.
        cursor = await self.collection.aggregate(pipeline, allowDiskUse=True)
        return [doc async for doc in cursor]

    async def counts_by_event_type(self) -> dict[str, int]:
        pipeline = [{"$group": {"_id": "$event_type", "n": {"$sum": 1}}}]
        cursor = await self.collection.aggregate(pipeline)
        return {doc["_id"]: doc["n"] async for doc in cursor}

    async def synthetic_ratio(self) -> float:
        total = await self.count()
        if not total:
            return 0.0
        synthetic = await self.count({"is_synthetic": True})
        return round(synthetic / total, 4)
