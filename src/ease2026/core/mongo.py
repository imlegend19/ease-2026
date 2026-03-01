"""Synchronous MongoDB connection helpers."""

__all__ = ["get_mongo_client", "get_mongo_database", "get_mongo_collection"]

import threading

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from ease2026.core.settings import settings


class MongoConnectionManager:
    _client_instance: MongoClient | None = None
    _lock = threading.Lock()
    _db_cache: dict[str, Database] = {}
    _coll_cache: dict[tuple[str, str], Collection] = {}

    @classmethod
    def get_client(cls) -> MongoClient:
        if cls._client_instance is None:
            with cls._lock:
                if cls._client_instance is None:
                    cls._client_instance = MongoClient(
                        settings.smartshark_mongo_uri,
                        uuidRepresentation="standard",
                    )
        return cls._client_instance

    @classmethod
    def get_database(cls, db_name: str | None = None) -> Database:
        target_db_name = db_name or settings.smartshark_mongo_db
        if target_db_name not in cls._db_cache:
            cls._db_cache[target_db_name] = cls.get_client()[target_db_name]
        return cls._db_cache[target_db_name]

    @classmethod
    def get_collection(
        cls,
        collection_name: str,
        db_name: str | None = None,
    ) -> Collection:
        target_db_name = db_name or settings.smartshark_mongo_db
        cache_key = (target_db_name, collection_name)
        if cache_key not in cls._coll_cache:
            db = cls.get_database(target_db_name)
            cls._coll_cache[cache_key] = db[collection_name]
        return cls._coll_cache[cache_key]


def get_mongo_client() -> MongoClient:
    return MongoConnectionManager.get_client()


def get_mongo_database(db_name: str | None = None) -> Database:
    return MongoConnectionManager.get_database(db_name=db_name)


def get_mongo_collection(collection_name: str, db_name: str | None = None) -> Collection:
    return MongoConnectionManager.get_collection(collection_name=collection_name, db_name=db_name)
