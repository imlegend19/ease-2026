"""Generate techno-social heroes via project-level median thresholding."""


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


@dataclass(frozen=True, slots=True)
class TechnoSocialSpec:
    name: str
    technical_dir_name: str
    social_dir_name: str
    technical_metric_column: str
    social_metric_column: str


SPECS: tuple[TechnoSocialSpec, ...] = (
    TechnoSocialSpec(
        name="commit_comments",
        technical_dir_name="commit_based",
        social_dir_name="comment_based",
        technical_metric_column="technical_commit_count",
        social_metric_column="social_comment_count",
    ),
    TechnoSocialSpec(
        name="commit_issues",
        technical_dir_name="commit_based",
        social_dir_name="issue_based",
        technical_metric_column="technical_commit_count",
        social_metric_column="social_issue_count",
    ),
    TechnoSocialSpec(
        name="file_comments",
        technical_dir_name="file_based",
        social_dir_name="comment_based",
        technical_metric_column="technical_file_count",
        social_metric_column="social_comment_count",
    ),
    TechnoSocialSpec(
        name="file_issues",
        technical_dir_name="file_based",
        social_dir_name="issue_based",
        technical_metric_column="technical_file_count",
        social_metric_column="social_issue_count",
    ),
    TechnoSocialSpec(
        name="loc_comments",
        technical_dir_name="loc_based",
        social_dir_name="comment_based",
        technical_metric_column="technical_loc_changed",
        social_metric_column="social_comment_count",
    ),
    TechnoSocialSpec(
        name="loc_issues",
        technical_dir_name="loc_based",
        social_dir_name="issue_based",
        technical_metric_column="technical_loc_changed",
        social_metric_column="social_issue_count",
    ),
)


class TechnoSocialMedianPipeline:
    @property
    def social_root(self) -> Path:
        return settings.interim_dir / "social"

    @property
    def technical_root(self) -> Path:
        return settings.interim_dir / "technical"

    @property
    def interim_root(self) -> Path:
        return settings.interim_dir / "techno_social"

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "techno_social"

    def run_all(self) -> list[Path]:
        output_paths: list[Path] = []
        for spec in SPECS:
            output_paths.append(self.run_spec(spec))
        return output_paths

    def run_spec(self, spec: TechnoSocialSpec) -> Path:
        technical_heroes = self._load_hero_author_counts(self.technical_root / spec.technical_dir_name)
        social_counts = self._load_project_author_counts(self.social_root / spec.social_dir_name)
        rows = self._build_rows(technical_heroes, social_counts)

        output_path = self.output_root / f"techno_social_heroes_{spec.name}.csv"
        self._write_csv(output_path, rows, spec)
        self._write_interim(spec.name, rows)

        logger.info(
            "Completed techno-social intersection",
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
        hero_flags: dict[str, bool] = self._load_pickle(hero_flags_path)
        return {
            project_name: author_counts
            for project_name, author_counts in top_authors.items()
            if hero_flags.get(project_name, False)
        }

    def _load_project_author_counts(self, source_dir: Path) -> ProjectAuthorCounts:
        counts_path = next(source_dir.glob("project_author_*_counts.pkl"), None)
        if counts_path is None:
            raise FileNotFoundError(f"Missing project-author count pickle in {source_dir}")
        return self._load_pickle(counts_path)

    @staticmethod
    def _project_median(author_counts: dict[Any, int]) -> int:
        if not author_counts:
            return 0
        values_desc = list(author_counts.values())
        return values_desc[len(values_desc) // 2]

    def _build_rows(
        self,
        technical_heroes: ProjectAuthorCounts,
        social_counts: ProjectAuthorCounts,
    ) -> list[tuple[str, Any, int, int, int]]:
        rows: list[tuple[str, Any, int, int, int]] = []

        for project_name, technical_authors in technical_heroes.items():
            project_social_counts = social_counts.get(project_name, {})
            if not project_social_counts:
                continue
            project_median = self._project_median(project_social_counts)

            for author_id, technical_metric in technical_authors.items():
                if author_id not in project_social_counts:
                    continue
                social_metric = project_social_counts[author_id]
                if social_metric >= project_median:
                    rows.append(
                        (
                            project_name,
                            author_id,
                            technical_metric,
                            social_metric,
                            project_median,
                        ),
                    )
        return rows

    def _write_csv(
        self,
        output_path: Path,
        rows: list[tuple[str, Any, int, int, int]],
        spec: TechnoSocialSpec,
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
                    "social_project_median",
                ],
            )
            writer.writerows(
                [project_name, str(author_id), technical_metric, social_metric, project_median]
                for project_name, author_id, technical_metric, social_metric, project_median in rows
            )

    def _write_interim(self, name: str, rows: list[tuple[str, Any, int, int, int]]) -> None:
        target_dir = self.interim_root / name
        ensure_directory(target_dir)

        by_project: dict[str, list[Any]] = {}
        for project_name, author_id, _, _, _ in rows:
            by_project.setdefault(project_name, []).append(author_id)

        with (target_dir / "techno_social_hero_authors.pkl").open("wb") as file:
            pickle.dump(by_project, file)

