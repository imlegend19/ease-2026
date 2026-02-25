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
        project_info_by_vcs_system = self._build_project_info_by_vcs_system(
            project_name_by_id=project_name_by_id
        )

        commit_collection = self.db["commit"]
        inserted_count = 0
        batch: list[dict[str, Any]] = []

        for commit_doc in commit_collection.find({}):
            vcs_system_id = commit_doc.get("vcs_system_id")
            project_info = project_info_by_vcs_system.get(vcs_system_id)
            if project_info is None:
                continue

            commit_doc["project_name_info"] = project_info["project_name_info"]
            commit_doc["project_id_info"] = project_info["project_id_info"]
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

    def build_comments_with_issue_and_project_info(
        self, drop_existing: bool = True
    ) -> DerivedCollectionStats:
        target = self.db[COMMENTS_WITH_ISSUE_COLLECTION]
        if drop_existing:
            self.db.drop_collection(COMMENTS_WITH_ISSUE_COLLECTION)
            target = self.db[COMMENTS_WITH_ISSUE_COLLECTION]

        project_name_by_id = self._build_project_name_by_id()
        project_info_by_issue_system = self._build_project_info_by_issue_system(
            project_name_by_id=project_name_by_id
        )
        issue_info_by_issue_id = self._build_issue_info_by_issue_id(
            project_info_by_issue_system=project_info_by_issue_system,
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

        identity_groups = self._build_identity_groups_from_people()
        inserted_count = 0
        batch: list[dict[str, Any]] = []

        if identity_groups:
            for merged_identity, people_ids in sorted(
                identity_groups.items(), key=lambda item: str(item[0])
            ):
                batch.append({"_id": merged_identity, "people": people_ids})
                if len(batch) >= self.batch_size:
                    inserted_count += self._insert_batch(target, batch)
                    batch.clear()
        else:
            unique_person_ids = self._collect_unique_person_ids()
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
            strategy="people_identity" if identity_groups else "activity_fallback",
        )
        return DerivedCollectionStats(
            collection_name=FINAL_IDENTITY_COLLECTION,
            inserted_count=inserted_count,
        )

    def _build_identity_groups_from_people(self) -> dict[ObjectId, list[ObjectId]]:
        if "people" not in self.db.list_collection_names():
            return {}

        grouped_people: dict[ObjectId, set[ObjectId]] = {}
        people_projection = {"_id": 1, "identity_id": 1}
        for person_doc in self.db["people"].find({}, people_projection):
            person_id = person_doc.get("_id")
            if not isinstance(person_id, ObjectId):
                continue

            identity_id = person_doc.get("identity_id")
            merged_identity = identity_id if isinstance(identity_id, ObjectId) else person_id
            grouped_people.setdefault(merged_identity, set()).add(person_id)

        return {
            merged_identity: sorted(people_ids, key=str)
            for merged_identity, people_ids in grouped_people.items()
            if people_ids
        }

    def _collect_unique_person_ids(self) -> list[ObjectId]:
        unique_ids: set[ObjectId] = set()

        commit_cursor = self.db["commit"].find({}, {"author_id": 1, "committer_id": 1})
        for commit_doc in commit_cursor:
            unique_ids.update(
                self._extract_object_ids(
                    [commit_doc.get("author_id"), commit_doc.get("committer_id")]
                )
            )

        issue_cursor = self.db["issue"].find(
            {}, {"assignee_id": 1, "creator_id": 1, "reporter_id": 1}
        )
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

        return sorted(unique_ids, key=str)

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

    def _build_project_info_by_vcs_system(
        self,
        project_name_by_id: dict[ObjectId, str],
    ) -> dict[ObjectId, dict[str, dict[str, Any]]]:
        mapping: dict[ObjectId, dict[str, dict[str, Any]]] = {}
        projection = {
            "_id": 1,
            "project_id": 1,
            "last_updated": 1,
            "repository_file": 1,
            "repository_type": 1,
            "url": 1,
        }
        for vcs_doc in self.db["vcs_system"].find({}, projection):
            vcs_id = vcs_doc.get("_id")
            project_id = vcs_doc.get("project_id")
            project_name = project_name_by_id.get(project_id)
            if (
                not isinstance(vcs_id, ObjectId)
                or not isinstance(project_id, ObjectId)
                or project_name is None
            ):
                continue

            mapping[vcs_id] = {
                "project_name_info": {
                    "project_id": project_id,
                    "name": project_name,
                },
                "project_id_info": {
                    "vcs_id": vcs_id,
                    "project_id": project_id,
                    "last_updated": vcs_doc.get("last_updated"),
                    "repository_file": vcs_doc.get("repository_file"),
                    "repository_type": vcs_doc.get("repository_type"),
                    "url": vcs_doc.get("url"),
                },
            }
        return mapping

    def _build_project_info_by_issue_system(
        self,
        project_name_by_id: dict[ObjectId, str],
    ) -> dict[ObjectId, dict[str, Any]]:
        mapping: dict[ObjectId, dict[str, Any]] = {}
        projection = {"_id": 1, "project_id": 1, "last_updated": 1, "url": 1}
        for issue_system_doc in self.db["issue_system"].find({}, projection):
            issue_system_id = issue_system_doc.get("_id")
            project_id = issue_system_doc.get("project_id")
            project_name = project_name_by_id.get(project_id)
            if (
                not isinstance(issue_system_id, ObjectId)
                or not isinstance(project_id, ObjectId)
                or project_name is None
            ):
                continue

            mapping[issue_system_id] = {
                "project_id": project_id,
                "project_name": project_name,
                "last_updated": issue_system_doc.get("last_updated"),
                "url": issue_system_doc.get("url"),
            }
        return mapping

    def _build_issue_info_by_issue_id(
        self,
        project_info_by_issue_system: dict[ObjectId, dict[str, Any]],
    ) -> dict[ObjectId, dict[str, Any]]:
        mapping: dict[ObjectId, dict[str, Any]] = {}
        issue_projection = {
            "_id": 1,
            "issue_system_id": 1,
            "issue_type": 1,
            "priority": 1,
            "status": 1,
            "assignee_id": 1,
            "creator_id": 1,
            "reporter_id": 1,
            "created_at": 1,
            "updated_at": 1,
            "desc": 1,
            "external_id": 1,
            "resolution": 1,
            "title": 1,
            "affects_versions": 1,
            "components": 1,
            "fix_versions": 1,
            "issue_links": 1,
            "labels": 1,
            "environment": 1,
            "original_time_estimate": 1,
            "parent_issue_id": 1,
        }
        for issue_doc in self.db["issue"].find({}, issue_projection):
            issue_id = issue_doc.get("_id")
            issue_system_id = issue_doc.get("issue_system_id")
            if not isinstance(issue_id, ObjectId) or not isinstance(issue_system_id, ObjectId):
                continue

            issue_system_info = project_info_by_issue_system.get(issue_system_id)
            if issue_system_info is None:
                continue

            issue_info: dict[str, Any] = {}
            for field_name in issue_projection:
                if field_name in {"_id"}:
                    continue
                if field_name in issue_doc:
                    issue_info[field_name] = issue_doc[field_name]

            project_id = issue_system_info["project_id"]
            project_name = issue_system_info["project_name"]
            issue_info["issue_id"] = issue_id
            mapping[issue_id] = {
                **issue_info,
                "project_name_info": {
                    "project_id": project_id,
                    "name": project_name,
                },
                "project_id_info": {
                    "issue_system_id": issue_system_id,
                    "project_id": project_id,
                    "last_updated": issue_system_info.get("last_updated"),
                    "url": issue_system_info.get("url"),
                },
            }

        return mapping
