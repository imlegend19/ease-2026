"""Common hero-selection rules used across pipelines."""

from __future__ import annotations

from typing import Any

ProjectAuthorCounts = dict[str, dict[Any, int]]
ProjectHeroFlags = dict[str, bool]


def extract_top_authors(
    project_author_counts: ProjectAuthorCounts,
    top_contributor_fraction: float,
) -> ProjectAuthorCounts:
    top_authors: ProjectAuthorCounts = {}
    for project_name, author_counts in project_author_counts.items():
        author_count = len(author_counts)
        top_limit = int(top_contributor_fraction * author_count)
        project_top: dict[Any, int] = {}
        for index, (author_id, contribution_count) in enumerate(author_counts.items()):
            if index == top_limit:
                break
            project_top[author_id] = contribution_count
        top_authors[project_name] = project_top
    return top_authors


def compute_hero_flags(
    project_author_counts: ProjectAuthorCounts,
    top_authors: ProjectAuthorCounts,
    hero_coverage_fraction: float,
) -> ProjectHeroFlags:
    hero_flags: ProjectHeroFlags = {}
    for project_name, author_counts in project_author_counts.items():
        project_total = sum(author_counts.values())
        top_total = sum(top_authors.get(project_name, {}).values())
        threshold = int(hero_coverage_fraction * project_total)
        hero_flags[project_name] = threshold <= top_total
    return hero_flags

