"""Social hero contribution extractors."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any

from ease2026.core.constants import COMMENTS_WITH_ISSUE_COLLECTION
from ease2026.core.mongo import get_mongo_collection

AuthorId = Hashable
ProjectContributionMap = dict[str, dict[AuthorId, int]]


def _sorted_project_contributions(project_contributions: ProjectContributionMap) -> ProjectContributionMap:
    sorted_output: ProjectContributionMap = {}
    for project_name, author_counts in sorted(project_contributions.items()):
        sorted_output[project_name] = dict(
            sorted(author_counts.items(), key=lambda item: (-item[1], str(item[0]))),
        )
    return sorted_output


def _extract_project_name(record: dict[str, Any]) -> str | None:
    issue_info = record.get("issue_info")
    if not isinstance(issue_info, dict):
        return None
    project_name_info = issue_info.get("project_name_info")
    if not isinstance(project_name_info, dict):
        return None
    project_name = project_name_info.get("name")
    return project_name if isinstance(project_name, str) and project_name else None


def compute_comment_count_contributions() -> ProjectContributionMap:
    project_author_counts: ProjectContributionMap = {}

    records = get_mongo_collection(COMMENTS_WITH_ISSUE_COLLECTION).find(
        {},
        {"author_id": 1, "issue_info.project_name_info.name": 1},
    )
    for record in records:
        author_id = record.get("author_id")
        project_name = _extract_project_name(record)
        if author_id is None or project_name is None:
            continue

        author_counts = project_author_counts.setdefault(project_name, {})
        author_counts[author_id] = author_counts.get(author_id, 0) + 1

    return _sorted_project_contributions(project_author_counts)


def compute_issue_participation_contributions() -> ProjectContributionMap:
    project_author_issue_ids: dict[str, dict[AuthorId, set[Any]]] = {}

    records = get_mongo_collection(COMMENTS_WITH_ISSUE_COLLECTION).find(
        {},
        {"author_id": 1, "issue_id": 1, "issue_info.project_name_info.name": 1},
    )
    for record in records:
        author_id = record.get("author_id")
        issue_id = record.get("issue_id")
        project_name = _extract_project_name(record)
        if author_id is None or issue_id is None or project_name is None:
            continue

        author_issue_ids = project_author_issue_ids.setdefault(project_name, {}).setdefault(
            author_id,
            set(),
        )
        author_issue_ids.add(issue_id)

    project_author_counts: ProjectContributionMap = {}
    for project_name, author_issue_ids in project_author_issue_ids.items():
        project_author_counts[project_name] = {
            author_id: len(issue_ids) for author_id, issue_ids in author_issue_ids.items()
        }

    return _sorted_project_contributions(project_author_counts)

