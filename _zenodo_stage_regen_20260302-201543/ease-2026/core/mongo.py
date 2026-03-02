"""Compatibility exports for the legacy ``core.mongo`` import path."""

from ease2026.core.mongo import (
    get_mongo_client,
    get_mongo_collection,
    get_mongo_database,
)

__all__ = ["get_mongo_client", "get_mongo_database", "get_mongo_collection"]
