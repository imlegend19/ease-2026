"""RQ2 overlap summary tables for base and type-level hero sets."""

from __future__ import annotations

import csv
import itertools
import math
from collections.abc import Hashable
from dataclasses import dataclass
from pathlib import Path

from ease2026.analysis.rq1 import HERO_CODE_ORDER, hero_csv_path, hero_type_from_code
from ease2026.core.logging import get_logger
from ease2026.core.settings import settings
from ease2026.hero.social import (
    compute_comment_count_contributions,
    compute_issue_participation_contributions,
)
from ease2026.hero.technical import (
    compute_commit_count_contributions,
    compute_file_touch_contributions,
    compute_loc_churn_contributions,
)
from ease2026.identity.canonical import load_identity_context

logger = get_logger(__name__)

TECHNICAL_METRIC_CODES: tuple[str, ...] = ("T1", "T2", "T3")
SOCIAL_METRIC_CODES: tuple[str, ...] = ("S1", "S2")
AuthorId = Hashable
ProjectContributionMap = dict[str, dict[AuthorId, int]]


@dataclass(frozen=True, slots=True)
class MembershipSet:
    project_author_pairs: frozenset[tuple[str, str]]
    projects: frozenset[str]
    project_authors: dict[str, frozenset[str]]


@dataclass(frozen=True, slots=True)
class CrossFacetCorrelation:
    project_name: str
    technical_code: str
    social_code: str
    n_developers_nonzero_union: int
    n_technical_nonzero: int
    n_social_nonzero: int
    spearman_rho: float


def _load_membership_set(hero_code: str) -> MembershipSet:
    csv_path = hero_csv_path(hero_code)
    if not csv_path.exists():
        logger.warning(
            "Hero CSV missing; using empty overlap set", hero_code=hero_code, csv_path=str(csv_path)
        )
        return MembershipSet(
            project_author_pairs=frozenset(),
            projects=frozenset(),
            project_authors={},
        )

    project_author_pairs: set[tuple[str, str]] = set()
    projects: set[str] = set()
    project_authors: dict[str, set[str]] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            project_name = str(row.get("project_name", "")).strip().lower()
            author_id = str(row.get("author_id", "")).strip()
            if not project_name or not author_id:
                continue
            projects.add(project_name)
            project_author_pairs.add((project_name, author_id))
            project_authors.setdefault(project_name, set()).add(author_id)

    return MembershipSet(
        project_author_pairs=frozenset(project_author_pairs),
        projects=frozenset(projects),
        project_authors={
            project_name: frozenset(author_ids)
            for project_name, author_ids in project_authors.items()
        },
    )


def _load_base_contribution_maps() -> dict[str, ProjectContributionMap]:
    reverse_identity_map, reverse_identity_resolver = load_identity_context()
    return {
        "T1": compute_commit_count_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "T2": compute_file_touch_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "T3": compute_loc_churn_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "S1": compute_comment_count_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "S2": compute_issue_participation_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
    }


def _jaccard_size(a: set, b: set) -> tuple[int, int, float]:
    intersection = len(a.intersection(b))
    union = len(a.union(b))
    score = float("nan") if union == 0 else (intersection / union)
    return intersection, union, score


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    fraction = position - lower
    return lower_value * (1 - fraction) + upper_value * fraction


def _iqr(values: list[float]) -> float:
    if not values:
        return float("nan")
    return _quantile(values, 0.75) - _quantile(values, 0.25)


def _mean(values: list[float]) -> float:
    if not values:
        return float("nan")
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    if not values:
        return float("nan")
    mean_value = _mean(values)
    return math.sqrt(sum((value - mean_value) ** 2 for value in values) / len(values))


def _average_ranks(values: list[float]) -> list[float]:
    if not values:
        return []

    indexed_values = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)

    lower = 0
    while lower < len(indexed_values):
        upper = lower
        tie_value = indexed_values[lower][1]
        while upper + 1 < len(indexed_values) and indexed_values[upper + 1][1] == tie_value:
            upper += 1

        # Rank positions are one-based; ties receive the mean rank.
        tie_rank = ((lower + 1) + (upper + 1)) / 2.0
        for tie_index in range(lower, upper + 1):
            original_position = indexed_values[tie_index][0]
            ranks[original_position] = tie_rank
        lower = upper + 1

    return ranks


def _pearson_correlation(values_x: list[float], values_y: list[float]) -> float:
    if not values_x or not values_y or len(values_x) != len(values_y):
        return float("nan")

    mean_x = _mean(values_x)
    mean_y = _mean(values_y)
    centered_x = [value - mean_x for value in values_x]
    centered_y = [value - mean_y for value in values_y]

    denominator_left = sum(value * value for value in centered_x)
    denominator_right = sum(value * value for value in centered_y)
    denominator = math.sqrt(denominator_left * denominator_right)
    if denominator == 0:
        return float("nan")

    numerator = sum(x * y for x, y in zip(centered_x, centered_y, strict=True))
    correlation = numerator / denominator
    return max(min(correlation, 1.0), -1.0)


def _spearman_correlation(values_x: list[float], values_y: list[float]) -> float:
    if len(values_x) != len(values_y) or len(values_x) < 2:
        return float("nan")
    return _pearson_correlation(_average_ranks(values_x), _average_ranks(values_y))


def _is_nan(value: float) -> bool:
    return math.isnan(value)


def _per_project_jaccard_values(set_a: MembershipSet, set_b: MembershipSet) -> list[float]:
    jaccards: list[float] = []
    projects_with_both = sorted(set(set_a.project_authors).intersection(set_b.project_authors))
    for project_name in projects_with_both:
        authors_a = set(set_a.project_authors.get(project_name, frozenset()))
        authors_b = set(set_b.project_authors.get(project_name, frozenset()))
        if not authors_a or not authors_b:
            continue
        _intersection, union, jaccard_value = _jaccard_size(authors_a, authors_b)
        if union == 0:
            continue
        jaccards.append(jaccard_value)
    return jaccards


class Rq2Analyzer:
    @property
    def output_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "final_tables"

    def run(self) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        memberships = {code: _load_membership_set(code) for code in HERO_CODE_ORDER}
        contribution_maps = _load_base_contribution_maps()

        technical_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_technical.csv",
            groups={code: memberships[code] for code in TECHNICAL_METRIC_CODES},
        )
        technical_per_project_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_technical_per_project.csv",
            groups={code: memberships[code] for code in TECHNICAL_METRIC_CODES},
            include_per_project_summary=True,
        )
        social_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_social.csv",
            groups={code: memberships[code] for code in SOCIAL_METRIC_CODES},
        )
        social_per_project_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_social_per_project.csv",
            groups={code: memberships[code] for code in SOCIAL_METRIC_CODES},
            include_per_project_summary=True,
        )
        type_path = self._write_type_overlap_table(
            memberships=memberships,
            output_name="rq2_overlap_type_groups.csv",
            include_per_project_summary=False,
        )
        type_per_project_path = self._write_type_overlap_table(
            memberships=memberships,
            output_name="rq2_overlap_type_groups_per_project.csv",
            include_per_project_summary=True,
        )
        cross_facet_per_project_path, cross_facet_summary_path = (
            self._write_cross_facet_correlation_tables(contribution_maps=contribution_maps)
        )

        logger.info(
            "Generated RQ2 final tables",
            technical_table=str(technical_path),
            technical_per_project_table=str(technical_per_project_path),
            social_table=str(social_path),
            social_per_project_table=str(social_per_project_path),
            type_table=str(type_path),
            type_per_project_table=str(type_per_project_path),
            cross_facet_per_project_table=str(cross_facet_per_project_path),
            cross_facet_summary_table=str(cross_facet_summary_path),
        )
        return {
            "rq2_overlap_technical": technical_path,
            "rq2_overlap_technical_per_project": technical_per_project_path,
            "rq2_overlap_social": social_path,
            "rq2_overlap_social_per_project": social_per_project_path,
            "rq2_overlap_type_groups": type_path,
            "rq2_overlap_type_groups_per_project": type_per_project_path,
            "rq2_cross_facet_spearman_per_project": cross_facet_per_project_path,
            "rq2_cross_facet_spearman_summary": cross_facet_summary_path,
        }

    def _write_pairwise_overlap_table(
        self,
        output_name: str,
        groups: dict[str, MembershipSet],
        include_per_project_summary: bool = False,
    ) -> Path:
        output_path = self.output_dir / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        labels = sorted(groups)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            header = [
                "group_a",
                "group_b",
                "a_project_author_pairs",
                "b_project_author_pairs",
                "pair_intersection",
                "pair_union",
                "pair_jaccard",
                "a_projects",
                "b_projects",
                "project_intersection",
                "project_union",
                "project_jaccard",
            ]
            if include_per_project_summary:
                header.extend(
                    [
                        "per_project_n",
                        "per_project_mean_jaccard",
                        "per_project_median_jaccard",
                        "per_project_std_jaccard",
                        "per_project_iqr_jaccard",
                    ]
                )
            writer.writerow(header)
            for label_a, label_b in itertools.combinations(labels, 2):
                set_a = groups[label_a]
                set_b = groups[label_b]
                pair_intersection, pair_union, pair_jaccard = _jaccard_size(
                    set(set_a.project_author_pairs),
                    set(set_b.project_author_pairs),
                )
                project_intersection, project_union, project_jaccard = _jaccard_size(
                    set(set_a.projects),
                    set(set_b.projects),
                )
                row: list[object] = [
                    label_a,
                    label_b,
                    len(set_a.project_author_pairs),
                    len(set_b.project_author_pairs),
                    pair_intersection,
                    pair_union,
                    pair_jaccard,
                    len(set_a.projects),
                    len(set_b.projects),
                    project_intersection,
                    project_union,
                    project_jaccard,
                ]
                if include_per_project_summary:
                    per_project_values = _per_project_jaccard_values(set_a, set_b)
                    row.extend(
                        [
                            len(per_project_values),
                            _mean(per_project_values),
                            _quantile(per_project_values, 0.5),
                            _std(per_project_values),
                            _iqr(per_project_values),
                        ]
                    )
                writer.writerow(row)
        return output_path

    def _write_type_overlap_table(
        self,
        memberships: dict[str, MembershipSet],
        output_name: str,
        include_per_project_summary: bool,
    ) -> Path:
        by_type_pairs: dict[str, set[tuple[str, str]]] = {}
        by_type_projects: dict[str, set[str]] = {}
        by_type_project_authors: dict[str, dict[str, set[str]]] = {}
        for hero_code, membership in memberships.items():
            hero_type = hero_type_from_code(hero_code)
            by_type_pairs.setdefault(hero_type, set()).update(membership.project_author_pairs)
            by_type_projects.setdefault(hero_type, set()).update(membership.projects)
            type_project_authors = by_type_project_authors.setdefault(hero_type, {})
            for project_name, authors in membership.project_authors.items():
                type_project_authors.setdefault(project_name, set()).update(authors)

        type_groups = {
            hero_type: MembershipSet(
                project_author_pairs=frozenset(project_author_pairs),
                projects=frozenset(by_type_projects.get(hero_type, set())),
                project_authors={
                    project_name: frozenset(author_ids)
                    for project_name, author_ids in by_type_project_authors.get(
                        hero_type, {}
                    ).items()
                },
            )
            for hero_type, project_author_pairs in by_type_pairs.items()
        }

        return self._write_pairwise_overlap_table(
            output_name=output_name,
            groups=type_groups,
            include_per_project_summary=include_per_project_summary,
        )

    def _collect_cross_facet_correlations(
        self,
        contribution_maps: dict[str, ProjectContributionMap],
    ) -> list[CrossFacetCorrelation]:
        rows: list[CrossFacetCorrelation] = []
        for technical_code in TECHNICAL_METRIC_CODES:
            technical_map = contribution_maps.get(technical_code, {})
            for social_code in SOCIAL_METRIC_CODES:
                social_map = contribution_maps.get(social_code, {})
                project_names = sorted(set(technical_map).union(social_map))

                for project_name in project_names:
                    technical_counts = technical_map.get(project_name, {})
                    social_counts = social_map.get(project_name, {})
                    author_ids = sorted(
                        set(technical_counts).union(social_counts),
                        key=lambda author_id: str(author_id),
                    )

                    technical_values: list[float] = []
                    social_values: list[float] = []
                    n_technical_nonzero = 0
                    n_social_nonzero = 0
                    for author_id in author_ids:
                        technical_value = float(technical_counts.get(author_id, 0))
                        social_value = float(social_counts.get(author_id, 0))
                        if technical_value != 0:
                            n_technical_nonzero += 1
                        if social_value != 0:
                            n_social_nonzero += 1
                        if technical_value == 0 and social_value == 0:
                            continue
                        technical_values.append(technical_value)
                        social_values.append(social_value)

                    rows.append(
                        CrossFacetCorrelation(
                            project_name=project_name,
                            technical_code=technical_code,
                            social_code=social_code,
                            n_developers_nonzero_union=len(technical_values),
                            n_technical_nonzero=n_technical_nonzero,
                            n_social_nonzero=n_social_nonzero,
                            spearman_rho=_spearman_correlation(technical_values, social_values),
                        )
                    )
        return rows

    def _write_cross_facet_correlation_tables(
        self,
        contribution_maps: dict[str, ProjectContributionMap],
    ) -> tuple[Path, Path]:
        per_project_rows = self._collect_cross_facet_correlations(contribution_maps)

        per_project_path = self.output_dir / "rq2_cross_facet_spearman_per_project.csv"
        with per_project_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "project_name",
                    "technical_code",
                    "social_code",
                    "n_developers_nonzero_union",
                    "n_technical_nonzero",
                    "n_social_nonzero",
                    "spearman_rho",
                ]
            )
            for row in per_project_rows:
                writer.writerow(
                    [
                        row.project_name,
                        row.technical_code,
                        row.social_code,
                        row.n_developers_nonzero_union,
                        row.n_technical_nonzero,
                        row.n_social_nonzero,
                        row.spearman_rho,
                    ]
                )

        summary_path = self.output_dir / "rq2_cross_facet_spearman_summary.csv"
        with summary_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "technical_code",
                    "social_code",
                    "n_projects_total",
                    "n_projects_with_defined_rho",
                    "spearman_rho_median",
                    "spearman_rho_iqr",
                ]
            )
            for technical_code in TECHNICAL_METRIC_CODES:
                for social_code in SOCIAL_METRIC_CODES:
                    pair_rows = [
                        row
                        for row in per_project_rows
                        if row.technical_code == technical_code and row.social_code == social_code
                    ]
                    pair_values = [
                        row.spearman_rho for row in pair_rows if not _is_nan(row.spearman_rho)
                    ]
                    writer.writerow(
                        [
                            technical_code,
                            social_code,
                            len(pair_rows),
                            len(pair_values),
                            _quantile(pair_values, 0.5),
                            _iqr(pair_values),
                        ]
                    )

        return per_project_path, summary_path


def run_rq2_analysis() -> dict[str, Path]:
    return Rq2Analyzer().run()
