"""RQ1 prevalence tables for base metrics and hero-type aggregates."""


import csv
from dataclasses import dataclass
from pathlib import Path

from ease2026.core.logging import get_logger
from ease2026.core.mongo import get_mongo_collection
from ease2026.core.settings import settings

logger = get_logger(__name__)

HERO_CODE_ORDER: tuple[str, ...] = (
    "S1",
    "S2",
    "T1",
    "T2",
    "T3",
    "ST1",
    "ST2",
    "ST3",
    "ST4",
    "ST5",
    "ST6",
    "TS1",
    "TS2",
    "TS3",
    "TS4",
    "TS5",
    "TS6",
    "SH1",
    "SH2",
    "SH3",
    "SH4",
    "SH5",
    "SH6",
)

BASE_METRIC_CODES: tuple[str, ...] = ("T1", "T2", "T3", "S1", "S2")
HERO_TYPE_ORDER: tuple[str, ...] = (
    "technical",
    "social",
    "sociotechnical",
    "technosocial",
    "super",
)


def hero_type_from_code(hero_code: str) -> str:
    if hero_code.startswith("ST"):
        return "sociotechnical"
    if hero_code.startswith("TS"):
        return "technosocial"
    if hero_code.startswith("SH"):
        return "super"
    if hero_code.startswith("T"):
        return "technical"
    if hero_code.startswith("S"):
        return "social"
    raise ValueError(f"Unsupported hero code: {hero_code}")


def hero_csv_path(hero_code: str) -> Path:
    root = settings.outputs_csv_dir / "heroes"
    if hero_code in {"S1", "S2", "T1", "T2", "T3"}:
        return root / hero_code / "heroes.csv"
    if hero_code.startswith("ST"):
        return root / "hybrid" / "sociotechnical" / f"{hero_code}.csv"
    if hero_code.startswith("TS"):
        return root / "hybrid" / "technosocial" / f"{hero_code}.csv"
    if hero_code.startswith("SH"):
        return root / "hybrid" / "super" / f"{hero_code}.csv"
    raise ValueError(f"Unsupported hero code: {hero_code}")


@dataclass(frozen=True, slots=True)
class HeroMembershipStats:
    hero_code: str
    hero_type: str
    project_count: int
    hero_member_rows: int
    unique_hero_authors: int
    unique_project_author_pairs: int
    projects: frozenset[str]
    project_author_pairs: frozenset[tuple[str, str]]


def _load_membership_stats(hero_code: str) -> HeroMembershipStats:
    csv_path = hero_csv_path(hero_code)
    if not csv_path.exists():
        logger.warning(
            "Hero CSV missing; using empty stats", hero_code=hero_code, csv_path=str(csv_path)
        )
        return HeroMembershipStats(
            hero_code=hero_code,
            hero_type=hero_type_from_code(hero_code),
            project_count=0,
            hero_member_rows=0,
            unique_hero_authors=0,
            unique_project_author_pairs=0,
            projects=frozenset(),
            project_author_pairs=frozenset(),
        )

    projects: set[str] = set()
    authors: set[str] = set()
    project_author_pairs: set[tuple[str, str]] = set()
    hero_member_rows = 0
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            project_name = str(row.get("project_name", "")).strip().lower()
            author_id = str(row.get("author_id", "")).strip()
            if not project_name or not author_id:
                continue
            hero_member_rows += 1
            projects.add(project_name)
            authors.add(author_id)
            project_author_pairs.add((project_name, author_id))

    return HeroMembershipStats(
        hero_code=hero_code,
        hero_type=hero_type_from_code(hero_code),
        project_count=len(projects),
        hero_member_rows=hero_member_rows,
        unique_hero_authors=len(authors),
        unique_project_author_pairs=len(project_author_pairs),
        projects=frozenset(projects),
        project_author_pairs=frozenset(project_author_pairs),
    )


def _load_total_project_count() -> int:
    names: set[str] = set()
    for doc in get_mongo_collection("project").find({}, {"name": 1}):
        normalized_name = str(doc.get("name", "")).strip().lower()
        if normalized_name:
            names.add(normalized_name)
    return len(names)


class Rq1Analyzer:
    @property
    def output_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "final_tables"

    def run(self) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        total_project_count = _load_total_project_count()
        stats_by_code = {code: _load_membership_stats(code) for code in HERO_CODE_ORDER}

        base_path = self._write_base_metric_table(
            total_project_count=total_project_count,
            stats_by_code=stats_by_code,
        )
        type_path = self._write_type_aggregate_table(
            total_project_count=total_project_count,
            stats_by_code=stats_by_code,
        )

        logger.info(
            "Generated RQ1 final tables",
            total_project_count=total_project_count,
            base_table=str(base_path),
            type_table=str(type_path),
        )
        return {
            "rq1_base_metric_prevalence": base_path,
            "rq1_hero_type_prevalence": type_path,
        }

    def _write_base_metric_table(
        self,
        total_project_count: int,
        stats_by_code: dict[str, HeroMembershipStats],
    ) -> Path:
        output_path = self.output_dir / "rq1_base_metric_prevalence.csv"
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "hero_code",
                    "hero_type",
                    "project_count_total",
                    "project_count_hero",
                    "project_prevalence_pct",
                    "hero_member_rows",
                    "unique_hero_authors",
                    "unique_project_author_pairs",
                ]
            )

            for hero_code in BASE_METRIC_CODES:
                stats = stats_by_code[hero_code]
                prevalence = (
                    float("nan")
                    if total_project_count == 0
                    else (stats.project_count / total_project_count) * 100
                )
                writer.writerow(
                    [
                        hero_code,
                        stats.hero_type,
                        total_project_count,
                        stats.project_count,
                        prevalence,
                        stats.hero_member_rows,
                        stats.unique_hero_authors,
                        stats.unique_project_author_pairs,
                    ]
                )
        return output_path

    def _write_type_aggregate_table(
        self,
        total_project_count: int,
        stats_by_code: dict[str, HeroMembershipStats],
    ) -> Path:
        stats_by_type: dict[str, list[HeroMembershipStats]] = {}
        for stats in stats_by_code.values():
            stats_by_type.setdefault(stats.hero_type, []).append(stats)

        output_path = self.output_dir / "rq1_hero_type_prevalence.csv"
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "hero_type",
                    "code_count",
                    "project_count_total",
                    "project_count_hero_any_metric",
                    "project_prevalence_pct",
                    "hero_member_rows_total",
                    "unique_hero_authors",
                    "unique_project_author_pairs",
                ]
            )

            for hero_type in HERO_TYPE_ORDER:
                type_stats = stats_by_type.get(hero_type, [])
                projects: set[str] = set()
                project_author_pairs: set[tuple[str, str]] = set()
                all_authors: set[str] = set()
                hero_member_rows_total = 0

                for stats in type_stats:
                    projects.update(stats.projects)
                    project_author_pairs.update(stats.project_author_pairs)
                    hero_member_rows_total += stats.hero_member_rows
                    all_authors.update(author for _, author in stats.project_author_pairs)

                project_count_hero_any = len(projects)
                prevalence = (
                    float("nan")
                    if total_project_count == 0
                    else (project_count_hero_any / total_project_count) * 100
                )
                writer.writerow(
                    [
                        hero_type,
                        len(type_stats),
                        total_project_count,
                        project_count_hero_any,
                        prevalence,
                        hero_member_rows_total,
                        len(all_authors),
                        len(project_author_pairs),
                    ]
                )
        return output_path


def run_rq1_analysis() -> dict[str, Path]:
    return Rq1Analyzer().run()
