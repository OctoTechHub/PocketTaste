"""Shared repository plumbing: model <-> BSON document translation."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from pymongo.asynchronous.collection import AsyncCollection

from app.data.mongo import MongoGateway

TModel = TypeVar("TModel", bound=BaseModel)


def to_document(model: BaseModel) -> dict[str, Any]:
    """Serialise a domain model for Mongo, dropping the driver-managed `_id`."""
    document = model.model_dump(mode="python")
    document.pop("_id", None)
    return document


def from_document(model_type: type[TModel], document: dict[str, Any] | None) -> TModel | None:
    if document is None:
        return None
    document.pop("_id", None)
    return model_type.model_validate(document)


class BaseRepository(Generic[TModel]):
    collection_name: str
    model_type: type[TModel]
    key_field: str

    def __init__(self, gateway: MongoGateway) -> None:
        self._gateway = gateway

    @property
    def collection(self) -> AsyncCollection:
        return self._gateway.database[self.collection_name]

    async def upsert(self, model: TModel) -> None:
        key = getattr(model, self.key_field)
        await self.collection.update_one(
            {self.key_field: key}, {"$set": to_document(model)}, upsert=True
        )

    async def upsert_many(self, models: list[TModel]) -> int:
        if not models:
            return 0
        from pymongo import UpdateOne

        operations = [
            UpdateOne(
                {self.key_field: getattr(model, self.key_field)},
                {"$set": to_document(model)},
                upsert=True,
            )
            for model in models
        ]
        result = await self.collection.bulk_write(operations, ordered=False)
        return (result.upserted_count or 0) + (result.modified_count or 0)

    async def get(self, key: str) -> TModel | None:
        document = await self.collection.find_one({self.key_field: key})
        return from_document(self.model_type, document)

    async def list_all(self, limit: int = 0, projection: dict | None = None) -> list[TModel]:
        cursor = self.collection.find({}, projection)
        if limit:
            cursor = cursor.limit(limit)
        return [self.model_type.model_validate(self._clean(doc)) async for doc in cursor]

    async def find(self, query: dict, limit: int = 0, sort: list[tuple[str, int]] | None = None) -> list[TModel]:
        cursor = self.collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return [self.model_type.model_validate(self._clean(doc)) async for doc in cursor]

    async def count(self, query: dict | None = None) -> int:
        return await self.collection.count_documents(query or {})

    async def exists(self, key: str) -> bool:
        return await self.collection.count_documents({self.key_field: key}, limit=1) > 0

    async def delete_all(self) -> int:
        result = await self.collection.delete_many({})
        return result.deleted_count

    @staticmethod
    def _clean(document: dict[str, Any]) -> dict[str, Any]:
        document.pop("_id", None)
        return document
