"""Materialize derived collections required by SANER/EASE hero pipelines."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from bson import ObjectId

from core.constants import (
    COMMENTS_WITH_ISSUE_COLLECTION,
    COMMIT_WITH_PROJECT_INFO_COLLECTION,
    FINAL_IDENTITY_COLLECTION,
)
from core.logging import get_logger
from core.mongo import get_mongo_database

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DerivedCollectionStats:
    collection_name: str
    inserted_count: int


class DerivedCollectionsPipeline:
    def __init__(self, batch_size: int = 10_000) -> None:
        self.batch_size = batch_size
        self.db = get_mongo_database()

    def build_commit_with_project_info(self, drop_existing: bool = True) -> DerivedCollectionStats:
        target = self.db[COMMIT_WITH_PROJECT_INFO_COLLECTION]
        if drop_existing:
            self.db.drop_collection(COMMIT_WITH_PROJECT_INFO_COLLECTION)
            target = self.db[COMMIT_WITH_PROJECT_INFO_COLLECTION]

        project_name_by_id = self._build_project_name_by_id()
        project_id_by_vcs_system = self._build_project_id_by_vcs_system()

        commit_collection = self.db["commit"]
        inserted_count = 0
        batch: list[dict[str, Any]] = []

        for commit_doc in commit_collection.find({}):
            vcs_system_id = commit_doc.get("vcs_system_id")
            project_id = project_id_by_vcs_system.get(vcs_system_id)
            project_name = project_name_by_id.get(project_id)
            if project_id is None or project_name is None:
                continue

            commit_doc["project_name_info"] = {"_id": project_id, "name": project_name}
            batch.append(commit_doc)

            if len(batch) >= self.batch_size:
                inserted_count += self._insert_batch(target, batch)
                batch.clear()

        if batch:
            inserted_count += self._insert_batch(target, batch)

        logger.info(
            "Materialized commit_with_project_info",
            inserted_count=inserted_count,
            collection=COMMIT_WITH_PROJECT_INFO_COLLECTION,
        )
        return DerivedCollectionStats(
            collection_name=COMMIT_WITH_PROJECT_INFO_COLLECTION,
            inserted_count=inserted_count,
        )

    def build_comments_with_issue_and_project_info(self, drop_existing: bool = True) -> DerivedCollectionStats:
        target = self.db[COMMENTS_WITH_ISSUE_COLLECTION]
        if drop_existing:
            self.db.drop_collection(COMMENTS_WITH_ISSUE_COLLECTION)
            target = self.db[COMMENTS_WITH_ISSUE_COLLECTION]

        project_name_by_id = self._build_project_name_by_id()
        project_id_by_issue_system = self._build_project_id_by_issue_system()
        issue_info_by_issue_id = self._build_issue_info_by_issue_id(
            project_id_by_issue_system=project_id_by_issue_system,
            project_name_by_id=project_name_by_id,
        )

        issue_comment_collection = self.db["issue_comment"]
        inserted_count = 0
        batch: list[dict[str, Any]] = []

        for comment_doc in issue_comment_collection.find({}):
            issue_id = comment_doc.get("issue_id")
            if issue_id is None:
                continue

            issue_info = issue_info_by_issue_id.get(issue_id)
            if issue_info is None:
                continue

            comment_doc["issue_info"] = issue_info
            batch.append(comment_doc)

            if len(batch) >= self.batch_size:
                inserted_count += self._insert_batch(target, batch)
                batch.clear()

        if batch:
            inserted_count += self._insert_batch(target, batch)

        logger.info(
            "Materialized comments_with_issue_and_project_info",
            inserted_count=inserted_count,
            collection=COMMENTS_WITH_ISSUE_COLLECTION,
        )
        return DerivedCollectionStats(
            collection_name=COMMENTS_WITH_ISSUE_COLLECTION,
            inserted_count=inserted_count,
        )

    def build_final_identity(self, drop_existing: bool = True) -> DerivedCollectionStats:
        target = self.db[FINAL_IDENTITY_COLLECTION]
        if drop_existing:
            self.db.drop_collection(FINAL_IDENTITY_COLLECTION)
            target = self.db[FINAL_IDENTITY_COLLECTION]

        unique_person_ids = self._collect_unique_person_ids()
        inserted_count = 0
        batch: list[dict[str, Any]] = []

        for person_id in unique_person_ids:
            batch.append({"_id": person_id, "people": [person_id]})
            if len(batch) >= self.batch_size:
                inserted_count += self._insert_batch(target, batch)
                batch.clear()

        if batch:
            inserted_count += self._insert_batch(target, batch)

        logger.info(
            "Materialized final_identity",
            inserted_count=inserted_count,
            collection=FINAL_IDENTITY_COLLECTION,
        )
        return DerivedCollectionStats(
            collection_name=FINAL_IDENTITY_COLLECTION,
            inserted_count=inserted_count,
        )

    def run_all(self, drop_existing: bool = True) -> list[DerivedCollectionStats]:
        return [
            self.build_commit_with_project_info(drop_existing=drop_existing),
            self.build_comments_with_issue_and_project_info(drop_existing=drop_existing),
            self.build_final_identity(drop_existing=drop_existing),
        ]

    def _build_project_name_by_id(self) -> dict[ObjectId, str]:
        mapping: dict[ObjectId, str] = {}
        for project_doc in self.db["project"].find({}, {"_id": 1, "name": 1}):
            project_id = project_doc.get("_id")
            project_name = project_doc.get("name")
            if isinstance(project_id, ObjectId) and isinstance(project_name, str) and project_name:
                mapping[project_id] = project_name
        return mapping

    def _build_project_id_by_vcs_system(self) -> dict[ObjectId, ObjectId]:
        mapping: dict[ObjectId, ObjectId] = {}
        for vcs_doc in self.db["vcs_system"].find({}, {"_id": 1, "project_id": 1}):
            vcs_id = vcs_doc.get("_id")
            project_id = vcs_doc.get("project_id")
            if isinstance(vcs_id, ObjectId) and isinstance(project_id, ObjectId):
                mapping[vcs_id] = project_id
        return mapping

    def _build_project_id_by_issue_system(self) -> dict[ObjectId, ObjectId]:
        mapping: dict[ObjectId, ObjectId] = {}
        for issue_system_doc in self.db["issue_system"].find({}, {"_id": 1, "project_id": 1}):
            issue_system_id = issue_system_doc.get("_id")
            project_id = issue_system_doc.get("project_id")
            if isinstance(issue_system_id, ObjectId) and isinstance(project_id, ObjectId):
                mapping[issue_system_id] = project_id
        return mapping

    def _build_issue_info_by_issue_id(
        self,
        project_id_by_issue_system: dict[ObjectId, ObjectId],
        project_name_by_id: dict[ObjectId, str],
    ) -> dict[ObjectId, dict[str, Any]]:
        mapping: dict[ObjectId, dict[str, Any]] = {}
        for issue_doc in self.db["issue"].find({}, {"_id": 1, "issue_system_id": 1, "priority": 1, "issue_type": 1, "status": 1}):
            issue_id = issue_doc.get("_id")
            issue_system_id = issue_doc.get("issue_system_id")
            if not isinstance(issue_id, ObjectId) or not isinstance(issue_system_id, ObjectId):
                continue

            project_id = project_id_by_issue_system.get(issue_system_id)
            project_name = project_name_by_id.get(project_id)
            if project_id is None or project_name is None:
                continue

            mapping[issue_id] = {
                "_id": issue_id,
                "priority": issue_doc.get("priority"),
                "issue_type": issue_doc.get("issue_type"),
                "status": issue_doc.get("status"),
                "project_name_info": {
                    "_id": project_id,
                    "name": project_name,
                },
            }

        return mapping

    def _collect_unique_person_ids(self) -> list[ObjectId]:
        unique_ids: set[ObjectId] = set()

        commit_cursor = self.db["commit"].find({}, {"author_id": 1, "committer_id": 1})
        for commit_doc in commit_cursor:
            unique_ids.update(self._extract_object_ids([commit_doc.get("author_id"), commit_doc.get("committer_id")]))

        issue_cursor = self.db["issue"].find({}, {"assignee_id": 1, "creator_id": 1, "reporter_id": 1})
        for issue_doc in issue_cursor:
            unique_ids.update(
                self._extract_object_ids(
                    [
                        issue_doc.get("assignee_id"),
                        issue_doc.get("creator_id"),
                        issue_doc.get("reporter_id"),
                    ],
                ),
            )

        comment_cursor = self.db["issue_comment"].find({}, {"author_id": 1})
        for comment_doc in comment_cursor:
            unique_ids.update(self._extract_object_ids([comment_doc.get("author_id")]))

        return sorted(unique_ids)

    @staticmethod
    def _extract_object_ids(values: Iterable[Any]) -> set[ObjectId]:
        output: set[ObjectId] = set()
        for value in values:
            if isinstance(value, ObjectId):
                output.add(value)
            elif isinstance(value, list):
                output.update(item for item in value if isinstance(item, ObjectId))
        return output

    @staticmethod
    def _insert_batch(target_collection, batch: list[dict[str, Any]]) -> int:
        if not batch:
            return 0
        result = target_collection.insert_many(list(batch), ordered=False)
        return len(result.inserted_ids)
