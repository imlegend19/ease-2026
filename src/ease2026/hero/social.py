"""Social hero contribution extractors."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any

from ease2026.core.constants import COMMENTS_WITH_ISSUE_COLLECTION
from ease2026.core.mongo import get_mongo_collection
from ease2026.identity.canonical import (
    load_identity_context,
    resolve_canonical_person_id,
)
from ease2026.identity.reverse_identity import ReverseIdentityMap, ReverseIdentityResolver

AuthorId = Hashable
ProjectContributionMap = dict[str, dict[AuthorId, int]]


def _sorted_project_contributions(
    project_contributions: ProjectContributionMap,
) -> ProjectContributionMap:
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


def compute_comment_count_contributions(
    reverse_identity_map: ReverseIdentityMap | None = None,
    reverse_identity_resolver: ReverseIdentityResolver | None = None,
) -> ProjectContributionMap:
    reverse_identity_map, reverse_identity_resolver = load_identity_context(
        reverse_identity_map=reverse_identity_map,
        reverse_identity_resolver=reverse_identity_resolver,
    )
    project_author_comment_ids: dict[str, dict[AuthorId, set[Any]]] = {}

    records = get_mongo_collection(COMMENTS_WITH_ISSUE_COLLECTION).find(
        {},
        {"_id": 1, "author_id": 1, "issue_info.project_name_info.name": 1},
    )
    for record in records:
        comment_id = record.get("_id")
        author_id = resolve_canonical_person_id(
            person_id=record.get("author_id"),
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        )
        project_name = _extract_project_name(record)
        if comment_id is None or author_id is None or project_name is None:
            continue

        author_comment_ids = project_author_comment_ids.setdefault(project_name, {}).setdefault(
            author_id,
            set(),
        )
        author_comment_ids.add(comment_id)

    project_author_counts: ProjectContributionMap = {}
    for project_name, author_comment_ids in project_author_comment_ids.items():
        project_author_counts[project_name] = {
            author_id: len(comment_ids) for author_id, comment_ids in author_comment_ids.items()
        }
    return _sorted_project_contributions(project_author_counts)


def compute_issue_participation_contributions(
    reverse_identity_map: ReverseIdentityMap | None = None,
    reverse_identity_resolver: ReverseIdentityResolver | None = None,
) -> ProjectContributionMap:
    reverse_identity_map, reverse_identity_resolver = load_identity_context(
        reverse_identity_map=reverse_identity_map,
        reverse_identity_resolver=reverse_identity_resolver,
    )
    project_author_issue_ids: dict[str, dict[AuthorId, set[Any]]] = {}

    records = get_mongo_collection(COMMENTS_WITH_ISSUE_COLLECTION).find(
        {},
        {"author_id": 1, "issue_id": 1, "issue_info.project_name_info.name": 1},
    )
    for record in records:
        author_id = resolve_canonical_person_id(
            person_id=record.get("author_id"),
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        )
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
