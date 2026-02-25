"""Asynchronous MongoDB connection helpers."""

from __future__ import annotations

__all__ = [
    "get_async_mongo_client",
    "get_async_mongo_database",
    "get_async_mongo_collection",
]

import threading
from typing import Any

try:
    from pymongo import AsyncMongoClient
    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase
except ImportError:  # pragma: no cover - depends on installed pymongo version
    AsyncMongoClient = None  # type: ignore[assignment]
    AsyncCollection = Any  # type: ignore[misc,assignment]
    AsyncDatabase = Any  # type: ignore[misc,assignment]

from core.settings import settings


class MongoAsyncConnectionManager:
    _client_instance: AsyncMongoClient | None = None
    _lock = threading.Lock()
    _db_cache: dict[str, AsyncDatabase] = {}
    _coll_cache: dict[tuple[str, str], AsyncCollection] = {}

    @classmethod
    async def get_client(cls) -> AsyncMongoClient:
        if AsyncMongoClient is None:
            raise RuntimeError(
                "Async Mongo client is unavailable in this PyMongo version. "
                "Upgrade PyMongo to a release that provides AsyncMongoClient.",
            )
        if cls._client_instance is None:
            with cls._lock:
                if cls._client_instance is None:
                    cls._client_instance = AsyncMongoClient(
                        settings.smartshark_mongo_uri,
                        uuidRepresentation="standard",
                    )
                    await cls._client_instance.aconnect()
        return cls._client_instance

    @classmethod
    async def get_database(cls, db_name: str | None = None) -> AsyncDatabase:
        target_db_name = db_name or settings.smartshark_mongo_db
        if target_db_name not in cls._db_cache:
            client = await cls.get_client()
            cls._db_cache[target_db_name] = client[target_db_name]
        return cls._db_cache[target_db_name]

    @classmethod
    async def get_collection(
        cls,
        collection_name: str,
        db_name: str | None = None,
    ) -> AsyncCollection:
        target_db_name = db_name or settings.smartshark_mongo_db
        cache_key = (target_db_name, collection_name)
        if cache_key not in cls._coll_cache:
            db = await cls.get_database(db_name=target_db_name)
            cls._coll_cache[cache_key] = db[collection_name]
        return cls._coll_cache[cache_key]


async def get_async_mongo_client() -> AsyncMongoClient:
    return await MongoAsyncConnectionManager.get_client()


async def get_async_mongo_database(db_name: str | None = None) -> AsyncDatabase:
    return await MongoAsyncConnectionManager.get_database(db_name=db_name)


async def get_async_mongo_collection(
    collection_name: str,
    db_name: str | None = None,
) -> AsyncCollection:
    return await MongoAsyncConnectionManager.get_collection(collection_name=collection_name, db_name=db_name)

