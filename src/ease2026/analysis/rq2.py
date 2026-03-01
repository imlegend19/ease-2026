"""RQ2 overlap summary tables for base and type-level hero sets."""

from __future__ import annotations

import csv
import itertools
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


def _load_membership_set(hero_code: str) -> MembershipSet:
    csv_path = hero_csv_path(hero_code)
    if not csv_path.exists():
        logger.warning(
            "Hero CSV missing; using empty overlap set", hero_code=hero_code, csv_path=str(csv_path)
        )
        return MembershipSet(project_author_pairs=frozenset(), projects=frozenset())

    project_author_pairs: set[tuple[str, str]] = set()
    projects: set[str] = set()
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            project_name = str(row.get("project_name", "")).strip().lower()
            author_id = str(row.get("author_id", "")).strip()
            if not project_name or not author_id:
                continue
            projects.add(project_name)
            project_author_pairs.add((project_name, author_id))

    return MembershipSet(
        project_author_pairs=frozenset(project_author_pairs),
        projects=frozenset(projects),
    )


def _jaccard_size(a: set, b: set) -> tuple[int, int, float]:
    intersection = len(a.intersection(b))
    union = len(a.union(b))
    score = float("nan") if union == 0 else (intersection / union)
    return intersection, union, score


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
        social_path = self._write_pairwise_overlap_table(
            output_name="rq2_overlap_social.csv",
            groups={code: memberships[code] for code in ("S1", "S2")},
        )
        type_path = self._write_type_overlap_table(memberships=memberships)

        logger.info(
            "Generated RQ2 final tables",
            technical_table=str(technical_path),
            social_table=str(social_path),
            type_table=str(type_path),
        )
        return {
            "rq2_overlap_technical": technical_path,
            "rq2_overlap_social": social_path,
            "rq2_overlap_type_groups": type_path,
        }

    def _write_pairwise_overlap_table(
        self,
        output_name: str,
        groups: dict[str, MembershipSet],
    ) -> Path:
        output_path = self.output_dir / output_name
        labels = sorted(groups)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
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
            )
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
                writer.writerow(
                    [
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
                )
        return output_path

    def _write_type_overlap_table(self, memberships: dict[str, MembershipSet]) -> Path:
        by_type_pairs: dict[str, set[tuple[str, str]]] = {}
        by_type_projects: dict[str, set[str]] = {}
        for hero_code, membership in memberships.items():
            hero_type = hero_type_from_code(hero_code)
            by_type_pairs.setdefault(hero_type, set()).update(membership.project_author_pairs)
            by_type_projects.setdefault(hero_type, set()).update(membership.projects)

        type_groups = {
            hero_type: MembershipSet(
                project_author_pairs=frozenset(project_author_pairs),
                projects=frozenset(by_type_projects.get(hero_type, set())),
            )
            for hero_type, project_author_pairs in by_type_pairs.items()
        }

        return self._write_pairwise_overlap_table(
            output_name="rq2_overlap_type_groups.csv",
            groups=type_groups,
        )


def run_rq2_analysis() -> dict[str, Path]:
    return Rq2Analyzer().run()
