"""MongoDB access. The only module that knows about pymongo directly."""
from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    if not settings.db_url:
        raise RuntimeError("DB_URL is not set. Configure server/.env")
    return MongoClient(settings.db_url, serverSelectionTimeoutMS=15_000)


def get_db() -> Database:
    # Database name comes from the connection string (…/PocketTaste?…).
    return get_client().get_default_database()
