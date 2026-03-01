"""Pareto-style rules for classifying hero projects."""

from __future__ import annotations

import math
from collections.abc import Hashable

AuthorId = Hashable
ContributionCounts = dict[AuthorId, int]


def _top_count_to_select(contributor_count: int, top_fraction: float) -> int:
    if contributor_count <= 0:
        return 0
    raw_limit = math.ceil(top_fraction * contributor_count)
    return min(max(raw_limit, 1), contributor_count)


def _sorted_contributors(counts: ContributionCounts) -> list[tuple[AuthorId, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))


def select_top_contributors(counts: ContributionCounts, top_fraction: float) -> ContributionCounts:
    if not counts:
        return {}

    selected_count = _top_count_to_select(len(counts), top_fraction)
    return dict(_sorted_contributors(counts)[:selected_count])


def is_hero_project(
    counts: ContributionCounts,
    top_fraction: float,
    coverage_fraction: float,
) -> bool:
    if not counts:
        return False

    total_work = sum(counts.values())
    if total_work <= 0:
        return False

    top_contributors = select_top_contributors(counts, top_fraction=top_fraction)
    top_work = sum(top_contributors.values())
    required_work = coverage_fraction * total_work
    return top_work >= required_work


def hero_project_and_heroes(
    counts: ContributionCounts,
    top_fraction: float,
    coverage_fraction: float,
) -> tuple[bool, ContributionCounts]:
    heroes = select_top_contributors(counts, top_fraction=top_fraction)
    total_work = sum(counts.values())
    if total_work <= 0:
        return False, heroes

    top_work = sum(heroes.values())
    required_work = coverage_fraction * total_work
    return top_work >= required_work, heroes

