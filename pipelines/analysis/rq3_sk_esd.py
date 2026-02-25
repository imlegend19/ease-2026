"""Optional RQ3 Scott-Knott ESD rankings with a deterministic mean-rank fallback."""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from pipelines.analysis.hero_catalog import HERO_TYPE_SPECS, PRIORITY_SEVERITIES
from pipelines.analysis.issue_metrics import IssueMetricByHero, IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_rankings import DEFAULT_SORT_DIRECTION_BY_METRIC

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Rq3SkEsdOutputPaths:
    ranking_csv_paths: dict[str, dict[str, Path]]
    input_matrix_csv_paths: dict[str, dict[str, Path]]


class Rq3ScottKnottEsdPipeline:
    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3" / "sk_esd"

    def run_all(self) -> Rq3SkEsdOutputPaths:
        ranking_paths: dict[str, dict[str, Path]] = {}
        input_paths: dict[str, dict[str, Path]] = {}

        for metric_name in ("fixed", "reopened"):
            ranking_paths[metric_name] = {}
            input_paths[metric_name] = {}
            for severity in PRIORITY_SEVERITIES:
                ranking_path, input_path = self.run_single(
                    metric_name=metric_name, severity=severity
                )
                ranking_paths[metric_name][severity] = ranking_path
                input_paths[metric_name][severity] = input_path

        return Rq3SkEsdOutputPaths(
            ranking_csv_paths=ranking_paths,
            input_matrix_csv_paths=input_paths,
        )

    def run_single(self, metric_name: str, severity: str) -> tuple[Path, Path]:
        if metric_name not in {"fixed", "reopened"}:
            raise ValueError(f"Unsupported metric '{metric_name}'")
        if severity not in PRIORITY_SEVERITIES:
            raise ValueError(f"Unsupported severity '{severity}'")

        ensure_directory(self.output_root)
        input_matrix_path = self.output_root / f"sk_esd_input_{metric_name}_{severity}.csv"
        ranking_path = self.output_root / f"sk_esd_ranking_{metric_name}_{severity}.csv"

        issue_metrics = IssueOutcomeMetricsPipeline()
        metric_by_hero = issue_metrics.load_metric_pickle(
            metric_name=metric_name, severity=severity
        )
        input_matrix = self._build_input_matrix(metric_by_hero)
        input_matrix.to_csv(input_matrix_path, index=False)

        ranking_df = self._compute_sk_esd_or_fallback(input_matrix, metric_name=metric_name)
        ranking_df.insert(0, "metric", metric_name)
        ranking_df.insert(1, "severity", severity)
        ranking_df.to_csv(ranking_path, index=False)

        return ranking_path, input_matrix_path

    @staticmethod
    def _build_input_matrix(metric_by_hero: IssueMetricByHero) -> pd.DataFrame:
        filtered_by_hero = {
            hero_code: {
                project_name: value
                for project_name, value in project_values.items()
                if value != 0.0
            }
            for hero_code, project_values in metric_by_hero.items()
        }

        non_empty_project_sets = [
            set(project_values.keys())
            for project_values in filtered_by_hero.values()
            if project_values
        ]
        if not non_empty_project_sets:
            return pd.DataFrame(columns=[spec.code for spec in HERO_TYPE_SPECS])

        common_projects = sorted(set.intersection(*non_empty_project_sets))
        if not common_projects:
            return pd.DataFrame(columns=[spec.code for spec in HERO_TYPE_SPECS])

        matrix_data: dict[str, list[float]] = {}
        for hero_spec in HERO_TYPE_SPECS:
            hero_code = hero_spec.code
            matrix_data[hero_code] = [
                filtered_by_hero.get(hero_code, {}).get(project_name, math.nan)
                for project_name in common_projects
            ]

        return pd.DataFrame(matrix_data)

    def _compute_sk_esd_or_fallback(
        self, input_matrix: pd.DataFrame, metric_name: str
    ) -> pd.DataFrame:
        if input_matrix.empty:
            return pd.DataFrame(columns=["hero_code", "rank", "method"])

        sk_esd_df = self._compute_sk_esd_ranking(input_matrix)
        if sk_esd_df is not None:
            return sk_esd_df

        sort_descending = DEFAULT_SORT_DIRECTION_BY_METRIC[metric_name]
        means = input_matrix.mean(axis=0, skipna=True).to_dict()
        ranked = sorted(means.items(), key=lambda item: item[1], reverse=sort_descending)
        return pd.DataFrame(
            {
                "hero_code": [hero_code for hero_code, _ in ranked],
                "rank": list(range(1, len(ranked) + 1)),
                "method": "mean_fallback",
            },
        )

    @staticmethod
    def _compute_sk_esd_ranking(input_matrix: pd.DataFrame) -> pd.DataFrame | None:
        try:
            from rpy2.robjects import pandas2ri
            from rpy2.robjects.packages import importr
        except Exception as exc:  # pragma: no cover - depends on R runtime
            logger.warning("Skipping ScottKnottESD (rpy2 unavailable)", error=str(exc))
            return None

        try:
            pandas2ri.activate()
            sk_package = importr("ScottKnottESD")
            result = sk_package.sk_esd(input_matrix)

            # Legacy SANER parsing pattern:
            # result[3] = column order (1-based), result[1] = rank values.
            column_order = [int(index) - 1 for index in np.array(result[3])]
            rank_values = [int(rank) for rank in np.array(result[1])]
            hero_codes = [input_matrix.columns[idx] for idx in column_order]

            if len(hero_codes) != len(rank_values):
                raise ValueError("ScottKnottESD output shape mismatch")

            return pd.DataFrame(
                {
                    "hero_code": hero_codes,
                    "rank": rank_values,
                    "method": "sk_esd",
                },
            )
        except Exception as exc:  # pragma: no cover - depends on R runtime and package shape
            logger.warning("ScottKnottESD execution failed; using fallback ranking", error=str(exc))
            return None
