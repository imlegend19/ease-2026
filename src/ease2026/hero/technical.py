"""Technical hero contribution extractors."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any

from ease2026.core.constants import COMMIT_WITH_PROJECT_INFO_COLLECTION, FILE_ACTION_COLLECTION
from ease2026.core.mongo import get_mongo_collection

AuthorId = Hashable
ProjectContributionMap = dict[str, dict[AuthorId, int]]
CommitProjectAuthorIndex = dict[Any, tuple[str, AuthorId]]


def _sorted_project_contributions(
    project_contributions: ProjectContributionMap,
) -> ProjectContributionMap:
    sorted_output: ProjectContributionMap = {}
    for project_name, author_counts in sorted(project_contributions.items()):
        sorted_output[project_name] = dict(
            sorted(author_counts.items(), key=lambda item: (-item[1], str(item[0]))),
        )
    return sorted_output


def _build_commit_project_author_index() -> CommitProjectAuthorIndex:
    commit_index: CommitProjectAuthorIndex = {}

    records = get_mongo_collection(COMMIT_WITH_PROJECT_INFO_COLLECTION).find(
        {},
        {"_id": 1, "author_id": 1, "project_name_info.name": 1},
    )
    for record in records:
        commit_id = record.get("_id")
        author_id = record.get("author_id")
        project_info = record.get("project_name_info", {})
        project_name = project_info.get("name") if isinstance(project_info, dict) else None

        if commit_id is None or author_id is None or not project_name:
            continue

        commit_index[commit_id] = (project_name, author_id)
        commit_index[str(commit_id)] = (project_name, author_id)

    return commit_index


def compute_commit_count_contributions() -> ProjectContributionMap:
    project_author_counts: ProjectContributionMap = {}

    records = get_mongo_collection(COMMIT_WITH_PROJECT_INFO_COLLECTION).find(
        {},
        {"author_id": 1, "project_name_info.name": 1},
    )
    for record in records:
        author_id = record.get("author_id")
        project_info = record.get("project_name_info", {})
        project_name = project_info.get("name") if isinstance(project_info, dict) else None

        if author_id is None or not project_name:
            continue

        author_counts = project_author_counts.setdefault(project_name, {})
        author_counts[author_id] = author_counts.get(author_id, 0) + 1

    return _sorted_project_contributions(project_author_counts)


def compute_file_touch_contributions() -> ProjectContributionMap:
    commit_index = _build_commit_project_author_index()
    project_author_files: dict[str, dict[AuthorId, set[Any]]] = {}

    file_actions = get_mongo_collection(FILE_ACTION_COLLECTION).find(
        {},
        {"commit_id": 1, "file_id": 1},
    )
    for record in file_actions:
        commit_id = record.get("commit_id")
        file_id = record.get("file_id")
        if commit_id is None or file_id is None:
            continue

        project_and_author = commit_index.get(commit_id) or commit_index.get(str(commit_id))
        if project_and_author is None:
            continue

        project_name, author_id = project_and_author
        author_files = project_author_files.setdefault(project_name, {}).setdefault(
            author_id, set()
        )
        author_files.add(file_id)

    project_author_counts: ProjectContributionMap = {}
    for project_name, author_files in project_author_files.items():
        project_author_counts[project_name] = {
            author_id: len(file_ids) for author_id, file_ids in author_files.items()
        }

    return _sorted_project_contributions(project_author_counts)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def compute_loc_churn_contributions() -> ProjectContributionMap:
    commit_index = _build_commit_project_author_index()
    project_author_counts: ProjectContributionMap = {}

    file_actions = get_mongo_collection(FILE_ACTION_COLLECTION).find(
        {},
        {"commit_id": 1, "lines_added": 1, "lines_deleted": 1},
    )
    for record in file_actions:
        commit_id = record.get("commit_id")
        if commit_id is None:
            continue

        project_and_author = commit_index.get(commit_id) or commit_index.get(str(commit_id))
        if project_and_author is None:
            continue

        project_name, author_id = project_and_author
        loc_churn = _to_int(record.get("lines_added")) + _to_int(record.get("lines_deleted"))

        author_counts = project_author_counts.setdefault(project_name, {})
        author_counts[author_id] = author_counts.get(author_id, 0) + loc_churn

    return _sorted_project_contributions(project_author_counts)
