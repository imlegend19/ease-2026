"""Shared extractors for technical hero pipelines."""

from typing import Any

from core.constants import COMMIT_WITH_PROJECT_INFO_COLLECTION
from core.mongo import get_mongo_collection
from identity.reverse_identity import ReverseIdentityMap, ReverseIdentityResolver

CommitProjectAuthorIndex = dict[Any, tuple[str, Any]]


def build_commit_project_author_index(
    reverse_identity_map: ReverseIdentityMap,
    reverse_identity_resolver: ReverseIdentityResolver,
) -> CommitProjectAuthorIndex:
    commit_index: CommitProjectAuthorIndex = {}
    commit_records = get_mongo_collection(COMMIT_WITH_PROJECT_INFO_COLLECTION).find(
        {},
        {"_id": 1, "author_id": 1, "project_name_info.name": 1},
    )

    for record in commit_records:
        commit_id = record.get("_id")
        author_person_id = record.get("author_id")
        project_info = record.get("project_name_info", {})
        project_name = project_info.get("name")

        if commit_id is None or author_person_id is None or not project_name:
            continue

        merged_author_id = reverse_identity_resolver.resolve_person_id(
            author_person_id, reverse_identity_map
        )
        commit_index[commit_id] = (project_name, merged_author_id)
        commit_index[str(commit_id)] = (project_name, merged_author_id)

    return commit_index
