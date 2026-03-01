"""Generic hero generation from contribution maps."""

from __future__ import annotations

import csv
from collections.abc import Hashable
from dataclasses import dataclass
from pathlib import Path

from ease2026.core.settings import settings
from ease2026.hero.rules import hero_project_and_heroes

AuthorId = Hashable
ProjectContributionMap = dict[str, dict[AuthorId, int]]
ProjectHeroFlags = dict[str, bool]
ProjectHeroMembers = dict[str, dict[AuthorId, int]]


@dataclass(frozen=True, slots=True)
class HeroGenerationResult:
    metric_name: str
    hero_project_flags: ProjectHeroFlags
    hero_members: ProjectHeroMembers
    csv_path: Path


def build_hero_flags_and_members(
    contribution_map: ProjectContributionMap,
    top_fraction: float,
    coverage_fraction: float,
) -> tuple[ProjectHeroFlags, ProjectHeroMembers]:
    hero_flags: ProjectHeroFlags = {}
    hero_members: ProjectHeroMembers = {}

    for project_name, author_counts in sorted(contribution_map.items()):
        is_hero, heroes = hero_project_and_heroes(
            counts=author_counts,
            top_fraction=top_fraction,
            coverage_fraction=coverage_fraction,
        )
        hero_flags[project_name] = is_hero
        if is_hero:
            hero_members[project_name] = heroes

    return hero_flags, hero_members


def write_hero_members_csv(hero_members: ProjectHeroMembers, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["project_name", "author_id", "metric_value"])

        for project_name in sorted(hero_members):
            author_counts = hero_members[project_name]
            for author_id, metric_value in sorted(
                author_counts.items(),
                key=lambda item: (-item[1], str(item[0])),
            ):
                writer.writerow([project_name, str(author_id), metric_value])

    return output_path


def generate_hero_outputs(
    contribution_map: ProjectContributionMap,
    metric_name: str,
    top_fraction: float,
    coverage_fraction: float,
    output_root: Path | None = None,
) -> HeroGenerationResult:
    hero_flags, hero_members = build_hero_flags_and_members(
        contribution_map=contribution_map,
        top_fraction=top_fraction,
        coverage_fraction=coverage_fraction,
    )

    base_output_root = output_root or (settings.outputs_csv_dir / "heroes")
    csv_path = base_output_root / metric_name / "heroes.csv"
    write_hero_members_csv(hero_members=hero_members, output_path=csv_path)

    return HeroGenerationResult(
        metric_name=metric_name,
        hero_project_flags=hero_flags,
        hero_members=hero_members,
        csv_path=csv_path,
    )

