"""SANER-style compatibility exports for RQ3 artifacts."""

from __future__ import annotations

import math
import pickle
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from pipelines.analysis.hero_catalog import ALL_SEVERITIES, HERO_TYPE_SPECS, PRIORITY_SEVERITIES
from pipelines.analysis.issue_metrics import IssueMetricByHero, IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_rankings import DEFAULT_SORT_DIRECTION_BY_METRIC, Rq3RankingPipeline
from pipelines.analysis.rq3_sk_esd import Rq3ScottKnottEsdPipeline

logger = get_logger(__name__)

LEGACY_HERO_PICKLE_SEQUENCE: tuple[tuple[str, str, str], ...] = (
    ("h1", "SH6", "superLOCIssues.csv"),
    ("h2", "SH5", "superLOCComments.csv"),
    ("h3", "SH4", "superFileIssues.csv"),
    ("h4", "SH3", "superFileComments.csv"),
    ("h5", "SH2", "superCommitIssues.csv"),
    ("h6", "SH1", "superCommitsComments.csv"),
    ("h7", "TS6", "technoSocialLOCIssueWise.csv"),
    ("h8", "TS5", "technoSocialLOCCommentsWise.csv"),
    ("h9", "TS4", "technoSocialFileIssueWise.csv"),
    ("h10", "TS3", "technoSocialFileCommentsWise.csv"),
    ("h11", "TS2", "technoSocialCommitIssueWise.csv"),
    ("h12", "TS1", "technoSocialCommitCommentWise.csv"),
    ("h13", "ST5", "sociotechnicalCommentsLOC.csv"),
    ("h14", "ST1", "sociotechnicalCommentsCommits.csv"),
    ("h15", "ST3", "sociotechnicalCommentsFiles.csv"),
    ("h16", "ST6", "sociotechnicalIssueLOC.csv"),
    ("h17", "ST4", "sociotechnicalIssueFiles.csv"),
    ("h18", "ST2", "sociotechnicalIssueCommits.csv"),
    ("h19", "T3", "technicalHeroesLOCWise.csv"),
    ("h20", "T2", "technicalHeroesFileWise.csv"),
    ("h21", "T1", "technicalHeroesCommitsWise.csv"),
    ("h22", "S2", "socialHeroesIssueWise.csv"),
    ("h23", "S1", "socialHeroesCommentsWise.csv"),
)

HERO_CODE_TO_LEGACY_LABEL: dict[str, str] = {
    hero_code: label for label, hero_code, _ in LEGACY_HERO_PICKLE_SEQUENCE
}
HERO_CODE_TO_LEGACY_PICKLE_BASENAME: dict[str, str] = {
    hero_code: pickle_basename for _, hero_code, pickle_basename in LEGACY_HERO_PICKLE_SEQUENCE
}

_RQ3_LEGACY_COLUMNS = [
    "metric",
    "severity",
    "severity_suffix",
    "method",
    "label",
    "hero_code",
    "pickle_file",
    "rank",
    "mean",
    "common_project_count",
]


def _legacy_severity_suffix(metric_name: str, severity: str) -> str:
    base_suffix = f"pkl_{metric_name}_issues"
    if severity == "all":
        return base_suffix
    return f"{base_suffix}_{severity}"


@dataclass(frozen=True, slots=True)
class Rq3LegacyOutputPaths:
    legacy_pickle_paths: dict[str, dict[str, dict[str, Path]]]
    mean_ranking_paths: dict[str, dict[str, Path]]
    mean_summary_path: Path
    sk_esd_paths: dict[str, dict[str, Path]]
    sk_esd_summary_path: Path
    kendall_paths: dict[str, Path]


class Rq3LegacyExportPipeline:
    @property
    def rq3_output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3"

    @property
    def legacy_output_root(self) -> Path:
        return self.rq3_output_root / "legacy"

    @property
    def legacy_pickle_root(self) -> Path:
        return settings.interim_dir / "analysis" / "rq3_legacy" / "pickle_files"

    @property
    def sk_esd_output_root(self) -> Path:
        return self.rq3_output_root / "sk_esd"

    def run_all(
        self,
        refresh_identity_cache: bool = False,
        regenerate_dependencies: bool = True,
    ) -> Rq3LegacyOutputPaths:
        if regenerate_dependencies:
            IssueOutcomeMetricsPipeline().run(
                refresh_identity_cache=refresh_identity_cache,
                write_interim=True,
                write_csv=True,
            )
            Rq3RankingPipeline().run_all()
            Rq3ScottKnottEsdPipeline().run_all()

        legacy_pickle_paths = self.export_legacy_issue_pickles()
        mean_paths, mean_summary_path = self.export_scott_knot_mean_rankings()
        sk_esd_paths, sk_esd_summary_path = self.export_scott_knot_esd_rankings()
        kendall_paths = self.export_kendall_tau()

        logger.info(
            "Generated RQ3 legacy exports",
            legacy_pickle_count=sum(
                len(paths_by_hero)
                for paths_by_metric in legacy_pickle_paths.values()
                for paths_by_hero in paths_by_metric.values()
            ),
            mean_output_count=sum(
                len(paths_by_severity) for paths_by_severity in mean_paths.values()
            ),
            sk_esd_output_count=sum(
                len(paths_by_severity) for paths_by_severity in sk_esd_paths.values()
            ),
            kendall_output_count=len(kendall_paths),
        )

        return Rq3LegacyOutputPaths(
            legacy_pickle_paths=legacy_pickle_paths,
            mean_ranking_paths=mean_paths,
            mean_summary_path=mean_summary_path,
            sk_esd_paths=sk_esd_paths,
            sk_esd_summary_path=sk_esd_summary_path,
            kendall_paths=kendall_paths,
        )

    def export_legacy_issue_pickles(
        self,
        metric_names: tuple[str, ...] = ("fixed", "reopened"),
    ) -> dict[str, dict[str, dict[str, Path]]]:
        ensure_directory(self.legacy_pickle_root)
        issue_metrics = IssueOutcomeMetricsPipeline()
        output_paths: dict[str, dict[str, dict[str, Path]]] = {}

        for metric_name in metric_names:
            if metric_name not in {"fixed", "reopened"}:
                raise ValueError(f"Unsupported metric '{metric_name}'")

            output_paths[metric_name] = {}
            for severity in ALL_SEVERITIES:
                severity_suffix = _legacy_severity_suffix(metric_name, severity)
                metric_by_hero = issue_metrics.load_metric_pickle(
                    metric_name=metric_name,
                    severity=severity,
                )

                output_paths[metric_name][severity] = {}
                for hero_spec in HERO_TYPE_SPECS:
                    hero_code = hero_spec.code
                    pickle_basename = HERO_CODE_TO_LEGACY_PICKLE_BASENAME[hero_code]
                    legacy_path = self.legacy_pickle_root / f"{pickle_basename}.{severity_suffix}.pkl"
                    project_values = dict(
                        sorted(metric_by_hero.get(hero_code, {}).items(), key=lambda item: item[0])
                    )
                    with legacy_path.open("wb") as file:
                        pickle.dump(project_values, file)
                    output_paths[metric_name][severity][hero_code] = legacy_path

        return output_paths

    def export_scott_knot_mean_rankings(self) -> tuple[dict[str, dict[str, Path]], Path]:
        ensure_directory(self.legacy_output_root)
        issue_metrics = IssueOutcomeMetricsPipeline()

        mean_source_by_metric = {
            metric_name: self._load_mean_ranking_source(metric_name)
            for metric_name in ("fixed", "reopened")
        }

        output_paths: dict[str, dict[str, Path]] = {"fixed": {}, "reopened": {}}
        summary_rows: list[dict[str, str | int | float | None]] = []

        for metric_name in ("fixed", "reopened"):
            source_df = mean_source_by_metric[metric_name]
            for severity in ALL_SEVERITIES:
                severity_suffix = _legacy_severity_suffix(metric_name, severity)
                output_path = self.legacy_output_root / f"scott_knot_{severity_suffix}.csv"
                output_paths[metric_name][severity] = output_path

                if severity == "all":
                    rows = self._build_mean_ranking_rows(
                        metric_name=metric_name,
                        severity=severity,
                        metric_by_hero=issue_metrics.load_metric_pickle(
                            metric_name=metric_name, severity=severity
                        ),
                    )
                else:
                    rows = self._rows_from_mean_source(
                        source_df=source_df,
                        metric_name=metric_name,
                        severity=severity,
                    )

                    if not rows:
                        rows = self._build_mean_ranking_rows(
                            metric_name=metric_name,
                            severity=severity,
                            metric_by_hero=issue_metrics.load_metric_pickle(
                                metric_name=metric_name, severity=severity
                            ),
                        )

                frame = pd.DataFrame(rows, columns=_RQ3_LEGACY_COLUMNS)
                frame.to_csv(output_path, index=False)
                summary_rows.extend(rows)

        summary_path = self.legacy_output_root / "scott_knot_summary.csv"
        pd.DataFrame(summary_rows, columns=_RQ3_LEGACY_COLUMNS).to_csv(summary_path, index=False)
        return output_paths, summary_path

    def export_scott_knot_esd_rankings(self) -> tuple[dict[str, dict[str, Path]], Path]:
        ensure_directory(self.legacy_output_root)
        issue_metrics = IssueOutcomeMetricsPipeline()
        sk_esd_pipeline = Rq3ScottKnottEsdPipeline()

        output_paths: dict[str, dict[str, Path]] = {"fixed": {}, "reopened": {}}
        summary_rows: list[dict[str, str | int | float | None]] = []

        for metric_name in ("fixed", "reopened"):
            for severity in ALL_SEVERITIES:
                severity_suffix = _legacy_severity_suffix(metric_name, severity)
                output_path = self.legacy_output_root / f"scott_knot_esd_{severity_suffix}.csv"
                output_paths[metric_name][severity] = output_path

                ranking_df, input_matrix = self._load_or_compute_sk_esd(
                    metric_name=metric_name,
                    severity=severity,
                    issue_metrics=issue_metrics,
                    sk_esd_pipeline=sk_esd_pipeline,
                )
                means_by_hero = (
                    input_matrix.mean(axis=0, skipna=True).to_dict() if not input_matrix.empty else {}
                )
                common_project_count = int(input_matrix.shape[0])

                rows: list[dict[str, str | int | float | None]] = []
                if not ranking_df.empty:
                    for row in ranking_df.sort_values(["rank", "hero_code"]).itertuples(index=False):
                        hero_code = str(row.hero_code)
                        rows.append(
                            {
                                "metric": metric_name,
                                "severity": severity,
                                "severity_suffix": severity_suffix,
                                "method": str(row.method),
                                "label": HERO_CODE_TO_LEGACY_LABEL.get(hero_code),
                                "hero_code": hero_code,
                                "pickle_file": HERO_CODE_TO_LEGACY_PICKLE_BASENAME.get(hero_code),
                                "rank": int(row.rank),
                                "mean": float(means_by_hero.get(hero_code, math.nan)),
                                "common_project_count": common_project_count,
                            }
                        )

                frame = pd.DataFrame(rows, columns=_RQ3_LEGACY_COLUMNS)
                frame.to_csv(output_path, index=False)
                summary_rows.extend(rows)

        summary_path = self.legacy_output_root / "scott_knot_esd_summary.csv"
        pd.DataFrame(summary_rows, columns=_RQ3_LEGACY_COLUMNS).to_csv(summary_path, index=False)
        return output_paths, summary_path

    def export_kendall_tau(self) -> dict[str, Path]:
        ensure_directory(self.legacy_output_root)

        source_to_target = {
            self.rq3_output_root / "kendall_tau_formatted_fixed.csv": self.legacy_output_root
            / "fixed_kendall_tau.csv",
            self.rq3_output_root / "kendall_tau_formatted_reopened.csv": self.legacy_output_root
            / "reopened_kendall_tau.csv",
            self.rq3_output_root / "kendall_tau_fixed.csv": self.legacy_output_root
            / "fixed_kendall_tau_values.csv",
            self.rq3_output_root / "kendall_tau_reopened.csv": self.legacy_output_root
            / "reopened_kendall_tau_values.csv",
            self.rq3_output_root / "kendall_tau_p_values_fixed.csv": self.legacy_output_root
            / "fixed_kendall_tau_p_values.csv",
            self.rq3_output_root / "kendall_tau_p_values_reopened.csv": self.legacy_output_root
            / "reopened_kendall_tau_p_values.csv",
        }

        output_paths: dict[str, Path] = {}
        for source_path, target_path in source_to_target.items():
            if not source_path.exists():
                raise FileNotFoundError(
                    f"Missing RQ3 ranking artifact: {source_path}. "
                    "Run `python -m scripts.analysis.generate_rq3_rankings` first."
                )
            shutil.copyfile(source_path, target_path)
            output_paths[target_path.name] = target_path

        return output_paths

    def _load_mean_ranking_source(self, metric_name: str) -> pd.DataFrame:
        source_path = self.rq3_output_root / f"mean_ranking_{metric_name}.csv"
        if not source_path.exists():
            return pd.DataFrame()
        return pd.read_csv(source_path)

    @staticmethod
    def _compute_project_intersection_means(
        metric_by_hero: IssueMetricByHero,
    ) -> tuple[dict[str, float], set[str]]:
        filtered_by_hero = {
            hero_code: {
                project_name: value for project_name, value in project_map.items() if value != 0.0
            }
            for hero_code, project_map in metric_by_hero.items()
        }

        non_empty_project_sets = [
            set(project_map.keys()) for project_map in filtered_by_hero.values() if project_map
        ]
        common_projects = (
            set.intersection(*non_empty_project_sets) if non_empty_project_sets else set()
        )

        mean_by_hero: dict[str, float] = {}
        for hero_spec in HERO_TYPE_SPECS:
            hero_code = hero_spec.code
            project_values = [
                filtered_by_hero.get(hero_code, {}).get(project_name)
                for project_name in common_projects
                if project_name in filtered_by_hero.get(hero_code, {})
            ]

            if not project_values:
                mean_by_hero[hero_code] = math.nan
            else:
                mean_by_hero[hero_code] = float(pd.Series(project_values).mean())

        return mean_by_hero, common_projects

    def _build_mean_ranking_rows(
        self,
        metric_name: str,
        severity: str,
        metric_by_hero: IssueMetricByHero,
    ) -> list[dict[str, str | int | float | None]]:
        severity_suffix = _legacy_severity_suffix(metric_name, severity)
        sort_descending = DEFAULT_SORT_DIRECTION_BY_METRIC[metric_name]
        mean_by_hero, common_projects = self._compute_project_intersection_means(metric_by_hero)
        ranked_items = sorted(
            [
                (hero_code, mean_value)
                for hero_code, mean_value in mean_by_hero.items()
                if not math.isnan(mean_value)
            ],
            key=lambda item: item[1],
            reverse=sort_descending,
        )

        rows: list[dict[str, str | int | float | None]] = []
        for rank, (hero_code, mean_value) in enumerate(ranked_items, start=1):
            rows.append(
                {
                    "metric": metric_name,
                    "severity": severity,
                    "severity_suffix": severity_suffix,
                    "method": "mean_ranking",
                    "label": HERO_CODE_TO_LEGACY_LABEL.get(hero_code),
                    "hero_code": hero_code,
                    "pickle_file": HERO_CODE_TO_LEGACY_PICKLE_BASENAME.get(hero_code),
                    "rank": rank,
                    "mean": mean_value,
                    "common_project_count": len(common_projects),
                }
            )

        return rows

    def _rows_from_mean_source(
        self,
        source_df: pd.DataFrame,
        metric_name: str,
        severity: str,
    ) -> list[dict[str, str | int | float | None]]:
        if source_df.empty:
            return []

        severity_df = source_df[source_df["severity"] == severity]
        if severity_df.empty:
            return []

        severity_suffix = _legacy_severity_suffix(metric_name, severity)
        rows: list[dict[str, str | int | float | None]] = []
        for row in severity_df.sort_values(["rank", "hero_code"]).itertuples(index=False):
            hero_code = str(row.hero_code)
            rows.append(
                {
                    "metric": metric_name,
                    "severity": severity,
                    "severity_suffix": severity_suffix,
                    "method": "mean_ranking",
                    "label": HERO_CODE_TO_LEGACY_LABEL.get(hero_code),
                    "hero_code": hero_code,
                    "pickle_file": HERO_CODE_TO_LEGACY_PICKLE_BASENAME.get(hero_code),
                    "rank": int(row.rank),
                    "mean": float(row.mean_value),
                    "common_project_count": int(row.common_project_count),
                }
            )

        return rows

    def _load_or_compute_sk_esd(
        self,
        metric_name: str,
        severity: str,
        issue_metrics: IssueOutcomeMetricsPipeline,
        sk_esd_pipeline: Rq3ScottKnottEsdPipeline,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if severity in PRIORITY_SEVERITIES:
            ranking_path = self.sk_esd_output_root / f"sk_esd_ranking_{metric_name}_{severity}.csv"
            input_path = self.sk_esd_output_root / f"sk_esd_input_{metric_name}_{severity}.csv"

            if ranking_path.exists() and input_path.exists():
                ranking_df = pd.read_csv(ranking_path)
                input_matrix = pd.read_csv(input_path)
                if {"hero_code", "rank"}.issubset(ranking_df.columns):
                    if "method" not in ranking_df.columns:
                        ranking_df["method"] = "sk_esd"
                    ranking_df = ranking_df[["hero_code", "rank", "method"]]
                    return ranking_df, input_matrix

        metric_by_hero = issue_metrics.load_metric_pickle(metric_name=metric_name, severity=severity)
        input_matrix = sk_esd_pipeline._build_input_matrix(metric_by_hero)  # noqa: SLF001
        ranking_df = sk_esd_pipeline._compute_sk_esd_or_fallback(  # noqa: SLF001
            input_matrix=input_matrix,
            metric_name=metric_name,
        )
        if ranking_df.empty:
            ranking_df = pd.DataFrame(columns=["hero_code", "rank", "method"])
        return ranking_df, input_matrix
