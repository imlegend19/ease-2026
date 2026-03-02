"""RQ2 overlap summary tables for base and type-level hero sets."""

from __future__ import annotations

import csv
import itertools
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

from ease2026.analysis.rq1 import HERO_CODE_ORDER, hero_csv_path, hero_type_from_code
from ease2026.core.logging import get_logger
from ease2026.core.settings import settings

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MembershipSet:
    project_author_pairs: frozenset[tuple[str, str]]
    projects: frozenset[str]
    authors_by_project: dict[str, frozenset[str]]


@dataclass(frozen=True, slots=True)
class PerProjectJaccardSummary:
    n_projects: int
    mean_jaccard: float
    median_jaccard: float
    std_jaccard: float
    iqr_jaccard: float


def _load_membership_set(hero_code: str) -> MembershipSet:
    csv_path = hero_csv_path(hero_code)
    if not csv_path.exists():
        logger.warning(
            "Hero CSV missing; using empty overlap set", hero_code=hero_code, csv_path=str(csv_path)
        )
        return MembershipSet(
            project_author_pairs=frozenset(),
            projects=frozenset(),
            authors_by_project={},
        )

    project_author_pairs: set[tuple[str, str]] = set()
    projects: set[str] = set()
    authors_by_project: dict[str, set[str]] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            project_name = str(row.get("project_name", "")).strip().lower()
            author_id = str(row.get("author_id", "")).strip()
            if not project_name or not author_id:
                continue
            projects.add(project_name)
            project_author_pairs.add((project_name, author_id))
            authors_by_project.setdefault(project_name, set()).add(author_id)

    return MembershipSet(
        project_author_pairs=frozenset(project_author_pairs),
        projects=frozenset(projects),
        authors_by_project={
            project_name: frozenset(authors)
            for project_name, authors in authors_by_project.items()
        },
    )


def _jaccard_size(a: set, b: set) -> tuple[int, int, float]:
    intersection = len(a.intersection(b))
    union = len(a.union(b))
    score = float("nan") if union == 0 else (intersection / union)
    return intersection, union, score


def _percentile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * quantile
    low_index = math.floor(position)
    high_index = math.ceil(position)
    if low_index == high_index:
        return sorted_values[low_index]

    low_value = sorted_values[low_index]
    high_value = sorted_values[high_index]
    interpolation = position - low_index
    return low_value + ((high_value - low_value) * interpolation)


def _summarize_per_project_jaccard(
    a: dict[str, frozenset[str]],
    b: dict[str, frozenset[str]],
) -> PerProjectJaccardSummary:
    project_scores: list[float] = []
    for project_name in set(a).intersection(b):
        authors_a = set(a[project_name])
        authors_b = set(b[project_name])
        if not authors_a or not authors_b:
            continue
        intersection = len(authors_a.intersection(authors_b))
        union = len(authors_a.union(authors_b))
        project_scores.append(intersection / union)

    if not project_scores:
        return PerProjectJaccardSummary(
            n_projects=0,
            mean_jaccard=float("nan"),
            median_jaccard=float("nan"),
            std_jaccard=float("nan"),
            iqr_jaccard=float("nan"),
        )

    sorted_scores = sorted(project_scores)
    q1 = _percentile(sorted_scores, 0.25)
    q3 = _percentile(sorted_scores, 0.75)
    return PerProjectJaccardSummary(
        n_projects=len(project_scores),
        mean_jaccard=statistics.fmean(project_scores),
        median_jaccard=statistics.median(project_scores),
        std_jaccard=statistics.pstdev(project_scores),
        iqr_jaccard=q3 - q1,
    )


class Rq2Analyzer:
    @property
    def output_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "final_tables"

    def run(self) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        memberships = {code: _load_membership_set(code) for code in HERO_CODE_ORDER}

        technical_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_technical.csv",
            groups={code: memberships[code] for code in ("T1", "T2", "T3")},
        )
        technical_per_project_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_technical_per_project.csv",
            groups={code: memberships[code] for code in ("T1", "T2", "T3")},
            include_per_project=True,
        )
        social_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_social.csv",
            groups={code: memberships[code] for code in ("S1", "S2")},
        )
        social_per_project_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_social_per_project.csv",
            groups={code: memberships[code] for code in ("S1", "S2")},
            include_per_project=True,
        )
        type_path = self._write_type_overlap_table(memberships=memberships)
        type_per_project_path = self._write_type_overlap_table(
            memberships=memberships,
            include_per_project=True,
        )

        logger.info(
            "Generated RQ2 final tables",
            technical_table=str(technical_path),
            technical_per_project_table=str(technical_per_project_path),
            social_table=str(social_path),
            social_per_project_table=str(social_per_project_path),
            type_table=str(type_path),
            type_per_project_table=str(type_per_project_path),
        )
        return {
            "rq2_overlap_technical": technical_path,
            "rq2_overlap_technical_per_project": technical_per_project_path,
            "rq2_overlap_social": social_path,
            "rq2_overlap_social_per_project": social_per_project_path,
            "rq2_overlap_type_groups": type_path,
            "rq2_overlap_type_groups_per_project": type_per_project_path,
        }

    def _write_pairwise_overlap_table(
        self,
        output_name: str,
        groups: dict[str, MembershipSet],
        *,
        include_per_project: bool = False,
    ) -> Path:
        output_path = self.output_dir / output_name
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
            if include_per_project:
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
                row = [
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
                if include_per_project:
                    per_project = _summarize_per_project_jaccard(
                        set_a.authors_by_project,
                        set_b.authors_by_project,
                    )
                    row.extend(
                        [
                            per_project.n_projects,
                            per_project.mean_jaccard,
                            per_project.median_jaccard,
                            per_project.std_jaccard,
                            per_project.iqr_jaccard,
                        ]
                    )
                writer.writerow(row)
        return output_path

    def _write_type_overlap_table(
        self,
        memberships: dict[str, MembershipSet],
        *,
        include_per_project: bool = False,
    ) -> Path:
        by_type_pairs: dict[str, set[tuple[str, str]]] = {}
        by_type_projects: dict[str, set[str]] = {}
        by_type_authors_by_project: dict[str, dict[str, set[str]]] = {}
        for hero_code, membership in memberships.items():
            hero_type = hero_type_from_code(hero_code)
            by_type_pairs.setdefault(hero_type, set()).update(membership.project_author_pairs)
            by_type_projects.setdefault(hero_type, set()).update(membership.projects)
            authors_by_project = by_type_authors_by_project.setdefault(hero_type, {})
            for project_name, authors in membership.authors_by_project.items():
                authors_by_project.setdefault(project_name, set()).update(authors)

        type_groups = {
            hero_type: MembershipSet(
                project_author_pairs=frozenset(project_author_pairs),
                projects=frozenset(by_type_projects.get(hero_type, set())),
                authors_by_project={
                    project_name: frozenset(authors)
                    for project_name, authors in by_type_authors_by_project.get(
                        hero_type,
                        {},
                    ).items()
                },
            )
            for hero_type, project_author_pairs in by_type_pairs.items()
        }

        return self._write_pairwise_overlap_table(
            output_name=(
                "rq2_overlap_type_groups_per_project.csv"
                if include_per_project
                else "rq2_overlap_type_groups.csv"
            ),
            groups=type_groups,
            include_per_project=include_per_project,
        )


def run_rq2_analysis() -> dict[str, Path]:
    return Rq2Analyzer().run()
