"""RQ2 overlap summary tables for base and type-level hero sets."""

from __future__ import annotations

import csv
import itertools
import math
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
    project_authors: dict[str, frozenset[str]]


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

        technical_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_technical.csv",
            groups={code: memberships[code] for code in ("T1", "T2", "T3")},
        )
        technical_per_project_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_technical_per_project.csv",
            groups={code: memberships[code] for code in ("T1", "T2", "T3")},
            include_per_project_summary=True,
        )
        social_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_social.csv",
            groups={code: memberships[code] for code in ("S1", "S2")},
        )
        social_per_project_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_social_per_project.csv",
            groups={code: memberships[code] for code in ("S1", "S2")},
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


def run_rq2_analysis() -> dict[str, Path]:
    return Rq2Analyzer().run()
