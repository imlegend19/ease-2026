"""Generate super heroes by intersecting social and technical hero sets."""

import csv
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings

logger = get_logger(__name__)

ProjectAuthorCounts = dict[str, dict[Any, int]]
ProjectHeroFlags = dict[str, bool]
ProjectSuperRows = list[tuple[str, Any, int, int]]


@dataclass(frozen=True, slots=True)
class SuperIntersectionSpec:
    name: str
    technical_dir_name: str
    social_dir_name: str
    technical_metric_column: str
    social_metric_column: str


SPECS: tuple[SuperIntersectionSpec, ...] = (
    SuperIntersectionSpec(
        name="commit_comments",
        technical_dir_name="commit_based",
        social_dir_name="comment_based",
        technical_metric_column="technical_commit_count",
        social_metric_column="social_comment_count",
    ),
    SuperIntersectionSpec(
        name="commit_issues",
        technical_dir_name="commit_based",
        social_dir_name="issue_based",
        technical_metric_column="technical_commit_count",
        social_metric_column="social_issue_count",
    ),
    SuperIntersectionSpec(
        name="file_comments",
        technical_dir_name="file_based",
        social_dir_name="comment_based",
        technical_metric_column="technical_file_count",
        social_metric_column="social_comment_count",
    ),
    SuperIntersectionSpec(
        name="file_issues",
        technical_dir_name="file_based",
        social_dir_name="issue_based",
        technical_metric_column="technical_file_count",
        social_metric_column="social_issue_count",
    ),
    SuperIntersectionSpec(
        name="loc_comments",
        technical_dir_name="loc_based",
        social_dir_name="comment_based",
        technical_metric_column="technical_loc_changed",
        social_metric_column="social_comment_count",
    ),
    SuperIntersectionSpec(
        name="loc_issues",
        technical_dir_name="loc_based",
        social_dir_name="issue_based",
        technical_metric_column="technical_loc_changed",
        social_metric_column="social_issue_count",
    ),
)


class SuperIntersectionPipeline:
    @property
    def social_root(self) -> Path:
        return settings.interim_dir / "social"

    @property
    def technical_root(self) -> Path:
        return settings.interim_dir / "technical"

    @property
    def interim_root(self) -> Path:
        return settings.interim_dir / "super"

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "super"

    def run_all(self) -> list[Path]:
        output_paths: list[Path] = []
        for spec in SPECS:
            output_paths.append(self.run_spec(spec))
        return output_paths

    def run_spec(self, spec: SuperIntersectionSpec) -> Path:
        technical_counts = self._load_hero_author_counts(
            self.technical_root / spec.technical_dir_name
        )
        social_counts = self._load_hero_author_counts(self.social_root / spec.social_dir_name)
        rows = self._build_rows(technical_counts, social_counts)

        output_path = self.output_root / f"super_heroes_{spec.name}.csv"
        self._write_csv(output_path, rows, spec)
        self._write_interim(spec.name, rows)

        logger.info(
            "Completed super heroes intersection",
            intersection=spec.name,
            project_count=len({row[0] for row in rows}),
            row_count=len(rows),
            output_csv=str(output_path),
        )
        return output_path

    @staticmethod
    def _load_pickle(file_path: Path):
        with file_path.open("rb") as file:
            return pickle.load(file)

    def _load_hero_author_counts(self, source_dir: Path) -> ProjectAuthorCounts:
        top_authors_path = next(source_dir.glob("project_top_author_*.pkl"), None)
        hero_flags_path = source_dir / "project_hero_flags.pkl"
        if top_authors_path is None:
            raise FileNotFoundError(f"Missing top-author pickle in {source_dir}")
        if not hero_flags_path.exists():
            raise FileNotFoundError(f"Missing hero flags pickle: {hero_flags_path}")

        top_authors: ProjectAuthorCounts = self._load_pickle(top_authors_path)
        hero_flags: ProjectHeroFlags = self._load_pickle(hero_flags_path)

        return {
            project_name: author_counts
            for project_name, author_counts in top_authors.items()
            if hero_flags.get(project_name, False)
        }

    @staticmethod
    def _build_rows(
        technical_counts: ProjectAuthorCounts,
        social_counts: ProjectAuthorCounts,
    ) -> ProjectSuperRows:
        rows: ProjectSuperRows = []
        for project_name, technical_authors in technical_counts.items():
            if project_name not in social_counts:
                continue

            social_authors = social_counts[project_name]
            for author_id, technical_value in technical_authors.items():
                if author_id not in social_authors:
                    continue
                social_value = social_authors[author_id]
                rows.append((project_name, author_id, technical_value, social_value))
        return rows

    def _write_csv(
        self,
        output_path: Path,
        rows: ProjectSuperRows,
        spec: SuperIntersectionSpec,
    ) -> None:
        ensure_directory(output_path.parent)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "project_name",
                    "author_id",
                    spec.technical_metric_column,
                    spec.social_metric_column,
                ],
            )
            writer.writerows(
                [project_name, str(author_id), technical_value, social_value]
                for project_name, author_id, technical_value, social_value in rows
            )

    def _write_interim(self, name: str, rows: ProjectSuperRows) -> None:
        target_dir = self.interim_root / name
        ensure_directory(target_dir)

        by_project: dict[str, list[Any]] = {}
        for project_name, author_id, _, _ in rows:
            by_project.setdefault(project_name, []).append(author_id)

        with (target_dir / "super_hero_authors.pkl").open("wb") as file:
            pickle.dump(by_project, file)
