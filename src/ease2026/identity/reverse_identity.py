"""Build and cache person -> merged-identity mapping."""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ease2026.core.constants import FINAL_IDENTITY_COLLECTION
from ease2026.core.logging import get_logger
from ease2026.core.mongo import get_mongo_collection
from ease2026.core.settings import settings

ReverseIdentityMap = dict[Any, Any]
logger = get_logger(__name__)


@dataclass(slots=True)
class ReverseIdentityResolver:
    cache_path: Path = settings.identity_cache_path

    def load_or_build(self, refresh_cache: bool = False) -> ReverseIdentityMap:
        if self.cache_path.exists() and not refresh_cache:
            return self._load_cache()

        reverse_identity_map = self._build_from_mongo()
        self._save_cache(reverse_identity_map)
        return reverse_identity_map

    @staticmethod
    def resolve_person_id(person_id: Any, reverse_identity_map: ReverseIdentityMap) -> Any:
        return reverse_identity_map.get(person_id, person_id)

    def _load_cache(self) -> ReverseIdentityMap:
        with self.cache_path.open("rb") as file:
            reverse_identity_map: ReverseIdentityMap = pickle.load(file)
        logger.info(
            "Loaded reverse identity cache",
            cache_path=str(self.cache_path),
            people_count=len(reverse_identity_map),
        )
        return reverse_identity_map

    def _build_from_mongo(self) -> ReverseIdentityMap:
        reverse_identity_map: ReverseIdentityMap = {}
        collection = get_mongo_collection(FINAL_IDENTITY_COLLECTION)

        for identity_doc in collection.find({}, {"_id": 1, "people": 1}):
            merged_identity = identity_doc.get("_id")
            for person_id in identity_doc.get("people", []):
                reverse_identity_map[person_id] = merged_identity

        logger.info("Built reverse identity map", people_count=len(reverse_identity_map))
        return reverse_identity_map

    def _save_cache(self, reverse_identity_map: ReverseIdentityMap) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("wb") as file:
            pickle.dump(reverse_identity_map, file)
        logger.info(
            "Saved reverse identity cache",
            cache_path=str(self.cache_path),
            people_count=len(reverse_identity_map),
        )
