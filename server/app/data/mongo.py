"""MongoDB connection lifecycle and index management.

Uses the native async driver shipped with pymongo >= 4.13 (`AsyncMongoClient`).
motor is deprecated upstream, so we do not depend on it.
"""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.core.errors import DependencyUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class Collections:
    CONTENT = "content_items"
    ACTIVITY = "activity_events"
    PROFILES = "content_profiles"
    FEATURES = "content_features"
    USERS = "user_profiles"
    INSIGHTS = "creator_insights"
    SIMILARITY = "similarity_reports"
    RUNS = "pipeline_runs"
    ACCOUNTS = "user_accounts"
    BLENDS = "blends"
    AUDIO = "content_audio"


#: (collection, keys, kwargs) — created idempotently at startup.
_INDEXES: list[tuple[str, list[tuple[str, int]], dict]] = [
    (Collections.CONTENT, [("content_id", ASCENDING)], {"unique": True, "name": "uq_content_id"}),
    (Collections.CONTENT, [("language", ASCENDING), ("genres", ASCENDING)], {"name": "ix_lang_genre"}),
    (Collections.CONTENT, [("creator_id", ASCENDING)], {"name": "ix_creator"}),
    # list_catalog sorts on this; without an index Mongo sorts in memory and a
    # large collection trips the 32MB limit before the projection is applied.
    (Collections.CONTENT, [("published_at", DESCENDING)], {"name": "ix_published"}),
    (Collections.AUDIO, [("content_id", ASCENDING)], {"unique": True, "name": "uq_audio_content"}),
    (Collections.ACTIVITY, [("event_id", ASCENDING)], {"unique": True, "name": "uq_event_id"}),
    (Collections.ACTIVITY, [("content_id", ASCENDING), ("occurred_at", DESCENDING)], {"name": "ix_content_time"}),
    (Collections.ACTIVITY, [("user_id", ASCENDING), ("occurred_at", DESCENDING)], {"name": "ix_user_time"}),
    (Collections.ACTIVITY, [("event_type", ASCENDING)], {"name": "ix_event_type"}),
    (Collections.PROFILES, [("content_id", ASCENDING)], {"unique": True, "name": "uq_profile_content"}),
    (Collections.PROFILES, [("cluster_id", ASCENDING)], {"name": "ix_cluster"}),
    (Collections.FEATURES, [("content_id", ASCENDING)], {"unique": True, "name": "uq_features_content"}),
    (Collections.USERS, [("user_id", ASCENDING)], {"unique": True, "name": "uq_user"}),
    (Collections.INSIGHTS, [("generated_at", DESCENDING)], {"name": "ix_insight_time"}),
    (Collections.SIMILARITY, [("computed_at", DESCENDING)], {"name": "ix_similarity_time"}),
    (Collections.RUNS, [("run_id", ASCENDING)], {"unique": True, "name": "uq_run_id"}),
    (Collections.RUNS, [("started_at", DESCENDING)], {"name": "ix_run_time"}),
    (Collections.ACCOUNTS, [("user_id", ASCENDING)], {"unique": True, "name": "uq_account_id"}),
    (Collections.ACCOUNTS, [("email", ASCENDING)], {"unique": True, "name": "uq_account_email"}),
]


class MongoGateway:
    """Owns the client. Nothing else in the app is allowed to construct one."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncMongoClient | None = None
        self._database: AsyncDatabase | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def database(self) -> AsyncDatabase:
        if self._database is None:
            raise DependencyUnavailableError("MongoDB is not connected. Set DB_URL in .env.")
        return self._database

    async def connect(self) -> bool:
        if not self._settings.mongo_enabled:
            logger.warning("No DB_URL configured — storage layer disabled.")
            return False
        try:
            self._client = AsyncMongoClient(
                self._settings.mongo_uri,
                serverSelectionTimeoutMS=self._settings.mongo_timeout_ms,
                tz_aware=True,
            )
            await self._client.admin.command("ping")
            self._database = self._client[self._settings.mongo_db_name]
            self._connected = True
            logger.info("MongoDB connected -> db=%s", self._settings.mongo_db_name)
            await self.ensure_indexes()
            return True
        except PyMongoError as exc:
            logger.error("MongoDB connection failed: %s", exc)
            self._client, self._database, self._connected = None, None, False
            return False

    async def ensure_indexes(self) -> None:
        for collection, keys, kwargs in _INDEXES:
            try:
                await self.database[collection].create_index(keys, **kwargs)
            except PyMongoError as exc:
                logger.warning("Index %s on %s skipped: %s", kwargs.get("name"), collection, exc)

    async def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._client, self._database, self._connected = None, None, False
