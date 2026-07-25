"""Data-access layer: Mongo gateway plus one repository per aggregate."""

from app.data.mongo import Collections, MongoGateway

__all__ = ["Collections", "MongoGateway"]
