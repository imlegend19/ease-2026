"""Hybrid hero generation (sociotechnical, technosocial, and super)."""

from __future__ import annotations

import csv
import math
from collections.abc import Hashable
from dataclasses import dataclass
from pathlib import Path

from ease2026.core.settings import settings

AuthorId = Hashable
ProjectContributionMap = dict[str, dict[AuthorId, int]]
ProjectThresholds = dict[str, int]
HybridRows = list[tuple[str, AuthorId, int]]


@dataclass(frozen=True, slots=True)
class HybridSpec:
    code: str
    technical_code: str
    social_code: str


SOCIOTECHNICAL_SPECS: tuple[HybridSpec, ...] = (
    HybridSpec(code="ST1", technical_code="T1", social_code="S1"),
    HybridSpec(code="ST2", technical_code="T1", social_code="S2"),
    HybridSpec(code="ST3", technical_code="T2", social_code="S1"),
    HybridSpec(code="ST4", technical_code="T2", social_code="S2"),
    HybridSpec(code="ST5", technical_code="T3", social_code="S1"),
    HybridSpec(code="ST6", technical_code="T3", social_code="S2"),
)

TECHNOSOCIAL_SPECS: tuple[HybridSpec, ...] = (
    HybridSpec(code="TS1", technical_code="T1", social_code="S1"),
    HybridSpec(code="TS2", technical_code="T1", social_code="S2"),
    HybridSpec(code="TS3", technical_code="T2", social_code="S1"),
    HybridSpec(code="TS4", technical_code="T2", social_code="S2"),
    HybridSpec(code="TS5", technical_code="T3", social_code="S1"),
    HybridSpec(code="TS6", technical_code="T3", social_code="S2"),
)

SUPER_SPECS: tuple[HybridSpec, ...] = (
    HybridSpec(code="SH1", technical_code="T1", social_code="S1"),
    HybridSpec(code="SH2", technical_code="T1", social_code="S2"),
    HybridSpec(code="SH3", technical_code="T2", social_code="S1"),
    HybridSpec(code="SH4", technical_code="T2", social_code="S2"),
    HybridSpec(code="SH5", technical_code="T3", social_code="S1"),
    HybridSpec(code="SH6", technical_code="T3", social_code="S2"),
)


def project_quantile_threshold(author_counts: dict[AuthorId, int], quantile: float) -> int | None:
    if not author_counts:
        return None

    values = sorted(author_counts.values())
    index = int(math.floor((len(values) - 1) * quantile))
    index = min(max(index, 0), len(values) - 1)
    return values[index]


def project_quantile_thresholds(
    contribution_map: ProjectContributionMap,
    quantile: float,
) -> ProjectThresholds:
    thresholds: ProjectThresholds = {}
    for project_name, author_counts in contribution_map.items():
        threshold = project_quantile_threshold(author_counts, quantile)
        if threshold is not None:
            thresholds[project_name] = threshold
    return thresholds


def sociotechnical_heroes(
    social_heroes: ProjectContributionMap,
    technical_contributions: ProjectContributionMap,
    quantile: float = 0.5,
) -> ProjectContributionMap:
    output: ProjectContributionMap = {}
    technical_thresholds = project_quantile_thresholds(technical_contributions, quantile)

    for project_name, social_authors in social_heroes.items():
        project_technical = technical_contributions.get(project_name)
        technical_threshold = technical_thresholds.get(project_name)
        if not project_technical or technical_threshold is None:
            continue

        kept_authors: dict[AuthorId, int] = {}
        for author_id, social_metric in social_authors.items():
            technical_metric = project_technical.get(author_id)
            if technical_metric is None:
                continue
            if technical_metric >= technical_threshold:
                kept_authors[author_id] = social_metric

        if kept_authors:
            output[project_name] = dict(
                sorted(kept_authors.items(), key=lambda item: (-item[1], str(item[0]))),
            )

    return output


def technosocial_heroes(
    technical_heroes: ProjectContributionMap,
    social_contributions: ProjectContributionMap,
    quantile: float = 0.5,
) -> ProjectContributionMap:
    output: ProjectContributionMap = {}
    social_thresholds = project_quantile_thresholds(social_contributions, quantile)

    for project_name, technical_authors in technical_heroes.items():
        project_social = social_contributions.get(project_name)
        social_threshold = social_thresholds.get(project_name)
        if not project_social or social_threshold is None:
            continue

        kept_authors: dict[AuthorId, int] = {}
        for author_id, technical_metric in technical_authors.items():
            social_metric = project_social.get(author_id)
            if social_metric is None:
                continue
            if social_metric >= social_threshold:
                kept_authors[author_id] = technical_metric

        if kept_authors:
            output[project_name] = dict(
                sorted(kept_authors.items(), key=lambda item: (-item[1], str(item[0]))),
            )

    return output


def superheroes(
    technical_heroes: ProjectContributionMap,
    social_heroes: ProjectContributionMap,
) -> ProjectContributionMap:
    output: ProjectContributionMap = {}

    for project_name, technical_authors in technical_heroes.items():
        project_social = social_heroes.get(project_name)
        if not project_social:
            continue

        kept_authors: dict[AuthorId, int] = {}
        for author_id, technical_metric in technical_authors.items():
            if author_id in project_social:
                kept_authors[author_id] = technical_metric

        if kept_authors:
            output[project_name] = dict(
                sorted(kept_authors.items(), key=lambda item: (-item[1], str(item[0]))),
            )

    return output


def hybrid_rows(project_author_counts: ProjectContributionMap) -> HybridRows:
    rows: HybridRows = []
    for project_name in sorted(project_author_counts):
        for author_id, metric_value in sorted(
            project_author_counts[project_name].items(),
            key=lambda item: (-item[1], str(item[0])),
        ):
            rows.append((project_name, author_id, metric_value))
    return rows


def write_hybrid_csv(rows: HybridRows, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["project_name", "author_id", "metric_value"])
        writer.writerows(
            [project_name, str(author_id), metric_value]
            for project_name, author_id, metric_value in rows
        )
    return output_path


def hybrid_output_path(category: str, code: str) -> Path:
    return settings.outputs_csv_dir / "heroes" / "hybrid" / category / f"{code}.csv"


def generate_sociotechnical(
    spec: HybridSpec,
    hero_members_by_code: dict[str, ProjectContributionMap],
    contribution_map_by_code: dict[str, ProjectContributionMap],
    quantile: float = 0.5,
) -> tuple[str, Path, HybridRows]:
    social_heroes = hero_members_by_code.get(spec.social_code, {})
    technical_contributions = contribution_map_by_code.get(spec.technical_code, {})

    selected = sociotechnical_heroes(
        social_heroes=social_heroes,
        technical_contributions=technical_contributions,
        quantile=quantile,
    )
    rows = hybrid_rows(selected)
    output_path = hybrid_output_path("sociotechnical", spec.code)
    write_hybrid_csv(rows, output_path)
    return spec.code, output_path, rows


def generate_technosocial(
    spec: HybridSpec,
    hero_members_by_code: dict[str, ProjectContributionMap],
    contribution_map_by_code: dict[str, ProjectContributionMap],
    quantile: float = 0.5,
) -> tuple[str, Path, HybridRows]:
    technical_heroes = hero_members_by_code.get(spec.technical_code, {})
    social_contributions = contribution_map_by_code.get(spec.social_code, {})

    selected = technosocial_heroes(
        technical_heroes=technical_heroes,
        social_contributions=social_contributions,
        quantile=quantile,
    )
    rows = hybrid_rows(selected)
    output_path = hybrid_output_path("technosocial", spec.code)
    write_hybrid_csv(rows, output_path)
    return spec.code, output_path, rows


def generate_super(
    spec: HybridSpec,
    hero_members_by_code: dict[str, ProjectContributionMap],
) -> tuple[str, Path, HybridRows]:
    technical_heroes = hero_members_by_code.get(spec.technical_code, {})
    social_heroes = hero_members_by_code.get(spec.social_code, {})

    selected = superheroes(
        technical_heroes=technical_heroes,
        social_heroes=social_heroes,
    )
    rows = hybrid_rows(selected)
    output_path = hybrid_output_path("super", spec.code)
    write_hybrid_csv(rows, output_path)
    return spec.code, output_path, rows

