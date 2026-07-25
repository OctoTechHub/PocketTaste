"""Persistence boundaries. The rest of the app works with domain models and never
touches MongoDB documents directly."""
from __future__ import annotations

from app.db import get_db
from app.domain.models import BehaviorEvent, Series, User


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


class SeriesRepository:
    @property
    def _col(self):
        return get_db()["series"]

    def replace_all(self, series: list[Series]) -> None:
        self._col.delete_many({})
        if series:
            self._col.insert_many([s.model_dump() for s in series])

    def find_all(self) -> list[Series]:
        return [Series(**_clean(d)) for d in self._col.find()]

    def find_by_id(self, series_id: str) -> Series | None:
        doc = self._col.find_one({"id": series_id})
        return Series(**_clean(doc)) if doc else None

    def find_by_ids(self, ids: list[str]) -> list[Series]:
        return [Series(**_clean(d)) for d in self._col.find({"id": {"$in": ids}})]

    def count(self) -> int:
        return self._col.count_documents({})


class UserRepository:
    @property
    def _col(self):
        return get_db()["users"]

    def replace_all(self, users: list[User]) -> None:
        self._col.delete_many({})
        if users:
            self._col.insert_many([u.model_dump() for u in users])

    def find_all(self) -> list[User]:
        return [User(**_clean(d)) for d in self._col.find()]

    def find_by_id(self, user_id: str) -> User | None:
        doc = self._col.find_one({"id": user_id})
        return User(**_clean(doc)) if doc else None

    def upsert(self, user: User) -> None:
        self._col.update_one({"id": user.id}, {"$set": user.model_dump()}, upsert=True)


class EventRepository:
    @property
    def _col(self):
        return get_db()["events"]

    def replace_all(self, events: list[BehaviorEvent]) -> None:
        self._col.delete_many({})
        if events:
            self._col.insert_many([e.model_dump() for e in events])

    def append(self, event: BehaviorEvent) -> None:
        self._col.insert_one(event.model_dump())

    def find_by_user(self, user_id: str) -> list[BehaviorEvent]:
        docs = self._col.find({"user_id": user_id}).sort("ts", 1)
        return [BehaviorEvent(**_clean(d)) for d in docs]

    def find_all(self) -> list[BehaviorEvent]:
        return [BehaviorEvent(**_clean(d)) for d in self._col.find()]


series_repository = SeriesRepository()
user_repository = UserRepository()
event_repository = EventRepository()
