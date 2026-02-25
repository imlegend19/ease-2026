"""Generate socio-technical heroes via project-level median thresholding."""

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
class SocioTechnicalSpec:
    name: str
    social_dir_name: str
    technical_dir_name: str
    social_metric_column: str
    technical_metric_column: str


SPECS: tuple[SocioTechnicalSpec, ...] = (
    SocioTechnicalSpec(
        name="comments_commits",
        social_dir_name="comment_based",
        technical_dir_name="commit_based",
        social_metric_column="social_comment_count",
        technical_metric_column="technical_commit_count",
    ),
    SocioTechnicalSpec(
        name="comments_files",
        social_dir_name="comment_based",
        technical_dir_name="file_based",
        social_metric_column="social_comment_count",
        technical_metric_column="technical_file_count",
    ),
    SocioTechnicalSpec(
        name="comments_loc",
        social_dir_name="comment_based",
        technical_dir_name="loc_based",
        social_metric_column="social_comment_count",
        technical_metric_column="technical_loc_changed",
    ),
    SocioTechnicalSpec(
        name="issues_commits",
        social_dir_name="issue_based",
        technical_dir_name="commit_based",
        social_metric_column="social_issue_count",
        technical_metric_column="technical_commit_count",
    ),
    SocioTechnicalSpec(
        name="issues_files",
        social_dir_name="issue_based",
        technical_dir_name="file_based",
        social_metric_column="social_issue_count",
        technical_metric_column="technical_file_count",
    ),
    SocioTechnicalSpec(
        name="issues_loc",
        social_dir_name="issue_based",
        technical_dir_name="loc_based",
        social_metric_column="social_issue_count",
        technical_metric_column="technical_loc_changed",
    ),
)


class SocioTechnicalMedianPipeline:
    @property
    def social_root(self) -> Path:
        return settings.interim_dir / "social"

    @property
    def technical_root(self) -> Path:
        return settings.interim_dir / "technical"

    @property
    def interim_root(self) -> Path:
        return settings.interim_dir / "socio_technical"

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "socio_technical"

    def run_all(self) -> list[Path]:
        output_paths: list[Path] = []
        for spec in SPECS:
            output_paths.append(self.run_spec(spec))
        return output_paths

    def run_spec(self, spec: SocioTechnicalSpec) -> Path:
        social_heroes = self._load_hero_author_counts(self.social_root / spec.social_dir_name)
        technical_counts = self._load_project_author_counts(
            self.technical_root / spec.technical_dir_name
        )
        rows = self._build_rows(social_heroes, technical_counts)

        output_path = self.output_root / f"socio_technical_heroes_{spec.name}.csv"
        self._write_csv(output_path, rows, spec)
        self._write_interim(spec.name, rows)

        logger.info(
            "Completed socio-technical intersection",
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
        social_heroes: ProjectAuthorCounts,
        technical_counts: ProjectAuthorCounts,
    ) -> list[tuple[str, Any, int, int, int]]:
        rows: list[tuple[str, Any, int, int, int]] = []

        for project_name, social_authors in social_heroes.items():
            project_technical_counts = technical_counts.get(project_name, {})
            if not project_technical_counts:
                continue
            project_median = self._project_median(project_technical_counts)

            for author_id, social_metric in social_authors.items():
                if author_id not in project_technical_counts:
                    continue
                technical_metric = project_technical_counts[author_id]
                if technical_metric >= project_median:
                    rows.append(
                        (
                            project_name,
                            author_id,
                            social_metric,
                            technical_metric,
                            project_median,
                        ),
                    )
        return rows

    def _write_csv(
        self,
        output_path: Path,
        rows: list[tuple[str, Any, int, int, int]],
        spec: SocioTechnicalSpec,
    ) -> None:
        ensure_directory(output_path.parent)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "project_name",
                    "author_id",
                    spec.social_metric_column,
                    spec.technical_metric_column,
                    "technical_project_median",
                ],
            )
            writer.writerows(
                [project_name, str(author_id), social_metric, technical_metric, project_median]
                for project_name, author_id, social_metric, technical_metric, project_median in rows
            )

    def _write_interim(self, name: str, rows: list[tuple[str, Any, int, int, int]]) -> None:
        target_dir = self.interim_root / name
        ensure_directory(target_dir)

        by_project: dict[str, list[Any]] = {}
        for project_name, author_id, _, _, _ in rows:
            by_project.setdefault(project_name, []).append(author_id)

        with (target_dir / "socio_technical_hero_authors.pkl").open("wb") as file:
            pickle.dump(by_project, file)
