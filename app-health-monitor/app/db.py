"""Conexão com o MongoDB e criação dos índices."""

from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from app.config import get_settings


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(settings.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=5000)


def get_db() -> Database:
    return get_client()[get_settings().mongo_db]


def ensure_indexes(db: Database) -> None:
    """Cria os índices. O índice TTL apaga checagens antigas automaticamente."""
    settings = get_settings()
    db.services.create_index([("url", ASCENDING)], unique=True)
    db.checks.create_index([("service_id", ASCENDING), ("ts", DESCENDING)])
    db.checks.create_index("ts", expireAfterSeconds=settings.retention_days * 86400)
