"""RQ3 analysis: mean-based hero rankings and Kendall Tau stability checks."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from pipelines.analysis.hero_catalog import HERO_TYPE_SPECS, PRIORITY_SEVERITIES
from pipelines.analysis.issue_metrics import IssueMetricByHero, IssueOutcomeMetricsPipeline

logger = get_logger(__name__)

DEFAULT_SORT_DIRECTION_BY_METRIC: dict[str, bool] = {
    "fixed": True,
    "reopened": False,
}


@dataclass(frozen=True, slots=True)
class Rq3MetricOutputPaths:
    mean_ranking_csv_path: Path
    kendall_tau_csv_path: Path
    kendall_p_value_csv_path: Path
    kendall_formatted_csv_path: Path


@dataclass(frozen=True, slots=True)
class Rq3OutputPaths:
    fixed: Rq3MetricOutputPaths
    reopened: Rq3MetricOutputPaths


class Rq3RankingPipeline:
    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3"

    def run_all(self) -> Rq3OutputPaths:
        fixed_outputs = self.run_metric(
            metric_name="fixed",
            sort_descending=DEFAULT_SORT_DIRECTION_BY_METRIC["fixed"],
        )
        reopened_outputs = self.run_metric(
            metric_name="reopened",
            sort_descending=DEFAULT_SORT_DIRECTION_BY_METRIC["reopened"],
        )
        return Rq3OutputPaths(fixed=fixed_outputs, reopened=reopened_outputs)

    def run_metric(self, metric_name: str, sort_descending: bool) -> Rq3MetricOutputPaths:
        if metric_name not in {"fixed", "reopened"}:
            raise ValueError(f"Unsupported metric '{metric_name}'")

        issue_metrics = IssueOutcomeMetricsPipeline()
        ensure_directory(self.output_root)

        mean_ranking_path = self.output_root / f"mean_ranking_{metric_name}.csv"
        kendall_tau_path = self.output_root / f"kendall_tau_{metric_name}.csv"
        kendall_p_value_path = self.output_root / f"kendall_tau_p_values_{metric_name}.csv"
        kendall_formatted_path = self.output_root / f"kendall_tau_formatted_{metric_name}.csv"

        ranking_rows: list[tuple[str, str, int, str, float, int]] = []
        ranking_orders: dict[str, list[str]] = {}

        for severity in PRIORITY_SEVERITIES:
            metric_by_hero = issue_metrics.load_metric_pickle(metric_name=metric_name, severity=severity)
            mean_by_hero, common_projects = self._compute_project_intersection_means(metric_by_hero)
            ranked_items = sorted(
                [(hero_code, mean_value) for hero_code, mean_value in mean_by_hero.items() if not math.isnan(mean_value)],
                key=lambda item: item[1],
                reverse=sort_descending,
            )
            ranking_orders[severity] = [hero_code for hero_code, _ in ranked_items]

            for rank, (hero_code, mean_value) in enumerate(ranked_items, start=1):
                ranking_rows.append(
                    (
                        metric_name,
                        severity,
                        rank,
                        hero_code,
                        mean_value,
                        len(common_projects),
                    ),
                )

        self._write_ranking_csv(mean_ranking_path, ranking_rows)

        tau_df, p_value_df, formatted_df = self._compute_kendall_tables(ranking_orders)
        tau_df.to_csv(kendall_tau_path, float_format="%.6f")
        p_value_df.to_csv(kendall_p_value_path, float_format="%.6f")
        formatted_df.to_csv(kendall_formatted_path)

        logger.info(
            "Generated RQ3 ranking outputs",
            metric=metric_name,
            rankings=str(mean_ranking_path),
            kendall=str(kendall_tau_path),
        )

        return Rq3MetricOutputPaths(
            mean_ranking_csv_path=mean_ranking_path,
            kendall_tau_csv_path=kendall_tau_path,
            kendall_p_value_csv_path=kendall_p_value_path,
            kendall_formatted_csv_path=kendall_formatted_path,
        )

    @staticmethod
    def _compute_project_intersection_means(metric_by_hero: IssueMetricByHero) -> tuple[dict[str, float], set[str]]:
        filtered_by_hero = {
            hero_code: {project_name: value for project_name, value in project_map.items() if value != 0.0}
            for hero_code, project_map in metric_by_hero.items()
        }

        non_empty_project_sets = [
            set(project_map.keys())
            for project_map in filtered_by_hero.values()
            if project_map
        ]
        common_projects = set.intersection(*non_empty_project_sets) if non_empty_project_sets else set()

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
                mean_by_hero[hero_code] = float(np.mean(project_values))

        return mean_by_hero, common_projects

    @staticmethod
    def _write_ranking_csv(output_path: Path, ranking_rows: list[tuple[str, str, int, str, float, int]]) -> None:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "metric",
                    "severity",
                    "rank",
                    "hero_code",
                    "mean_value",
                    "common_project_count",
                ],
            )
            writer.writerows(ranking_rows)

    @staticmethod
    def _compute_kendall_tables(ranking_orders: dict[str, list[str]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        severities = list(PRIORITY_SEVERITIES)
        tau_matrix = pd.DataFrame(index=severities, columns=severities, dtype=float)
        p_value_matrix = pd.DataFrame(index=severities, columns=severities, dtype=float)

        for severity_a in severities:
            for severity_b in severities:
                if severity_a == severity_b:
                    tau_matrix.loc[severity_a, severity_b] = 1.0
                    p_value_matrix.loc[severity_a, severity_b] = 0.0
                    continue

                order_a = ranking_orders.get(severity_a, [])
                order_b = ranking_orders.get(severity_b, [])
                common_heroes = [hero_code for hero_code in order_a if hero_code in set(order_b)]

                if len(common_heroes) < 2:
                    tau_matrix.loc[severity_a, severity_b] = np.nan
                    p_value_matrix.loc[severity_a, severity_b] = np.nan
                    continue

                rank_a = [order_a.index(hero_code) + 1 for hero_code in common_heroes]
                rank_b = [order_b.index(hero_code) + 1 for hero_code in common_heroes]
                tau_value, p_value = kendalltau(rank_a, rank_b)
                tau_matrix.loc[severity_a, severity_b] = tau_value
                p_value_matrix.loc[severity_a, severity_b] = p_value

        formatted_df = tau_matrix.round(3).astype(str) + " (" + p_value_matrix.round(3).astype(str) + ")"
        return tau_matrix, p_value_matrix, formatted_df

