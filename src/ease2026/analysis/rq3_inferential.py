"""Inferential RQ3 outputs: mean rankings, Kendall tau, and Scott-Knott ESD."""

from __future__ import annotations

import csv
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scipy.stats import kendalltau

from ease2026.analysis.rq1 import HERO_CODE_ORDER
from ease2026.core.logging import get_logger
from ease2026.core.settings import settings
from ease2026.outcomes.definitions import FixerAttributionPolicy, VALID_PRIORITIES

logger = get_logger(__name__)

METRIC_ORDER: tuple[str, ...] = ("fix_rate", "reopen_rate")
SORT_DESCENDING_BY_METRIC: dict[str, bool] = {
    "fix_rate": True,
    "reopen_rate": False,
}


@dataclass(frozen=True, slots=True)
class InputMatrix:
    hero_codes: tuple[str, ...]
    project_names: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]


def _parse_float(value: str) -> float:
    normalized = value.strip().lower()
    if normalized in {"", "nan"}:
        return float("nan")
    return float(normalized)


def _is_nan(value: float) -> bool:
    return math.isnan(value)


def build_input_matrix(
    metric_by_hero: dict[str, dict[str, float]],
    hero_code_order: tuple[str, ...] = HERO_CODE_ORDER,
) -> InputMatrix:
    """Build a project-aligned matrix using the project intersection across non-empty heroes."""
    available_heroes = [
        hero_code
        for hero_code in hero_code_order
        if hero_code in metric_by_hero and metric_by_hero[hero_code]
    ]
    if not available_heroes:
        return InputMatrix(hero_codes=tuple(), project_names=tuple(), rows=tuple())

    project_sets = [set(metric_by_hero[hero_code]) for hero_code in available_heroes]
    common_projects = sorted(set.intersection(*project_sets)) if project_sets else []
    if not common_projects:
        return InputMatrix(hero_codes=tuple(available_heroes), project_names=tuple(), rows=tuple())

    rows: list[tuple[float, ...]] = []
    for project_name in common_projects:
        rows.append(
            tuple(float(metric_by_hero[hero_code][project_name]) for hero_code in available_heroes)
        )

    return InputMatrix(
        hero_codes=tuple(available_heroes),
        project_names=tuple(common_projects),
        rows=tuple(rows),
    )


def compute_mean_ranking(
    input_matrix: InputMatrix,
    metric_name: str,
) -> list[tuple[int, str, float]]:
    """Compute a rank order from per-hero mean values."""
    if metric_name not in SORT_DESCENDING_BY_METRIC:
        raise ValueError(f"Unsupported metric: {metric_name}")

    if not input_matrix.hero_codes or not input_matrix.rows:
        return []

    means: dict[str, float] = {}
    row_count = len(input_matrix.rows)
    for column_index, hero_code in enumerate(input_matrix.hero_codes):
        means[hero_code] = sum(row[column_index] for row in input_matrix.rows) / row_count

    ranked = sorted(
        means.items(),
        key=lambda item: item[1],
        reverse=SORT_DESCENDING_BY_METRIC[metric_name],
    )
    return [
        (index, hero_code, mean_value) for index, (hero_code, mean_value) in enumerate(ranked, 1)
    ]


def compute_kendall_tables(
    ranking_order_by_severity: dict[str, list[str]],
    severity_order: tuple[str, ...] = VALID_PRIORITIES,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, str]]]:
    """Compute Kendall tau and p-value matrices across severities."""
    tau_table: dict[str, dict[str, float]] = {
        severity: {other: float("nan") for other in severity_order} for severity in severity_order
    }
    p_value_table: dict[str, dict[str, float]] = {
        severity: {other: float("nan") for other in severity_order} for severity in severity_order
    }

    for severity_a in severity_order:
        for severity_b in severity_order:
            if severity_a == severity_b:
                tau_table[severity_a][severity_b] = 1.0
                p_value_table[severity_a][severity_b] = 0.0
                continue

            order_a = ranking_order_by_severity.get(severity_a, [])
            order_b = ranking_order_by_severity.get(severity_b, [])
            if not order_a or not order_b:
                continue

            order_b_set = set(order_b)
            common_heroes = [hero_code for hero_code in order_a if hero_code in order_b_set]
            if len(common_heroes) < 2:
                continue

            rank_a = [order_a.index(hero_code) + 1 for hero_code in common_heroes]
            rank_b = [order_b.index(hero_code) + 1 for hero_code in common_heroes]
            tau_value, p_value = kendalltau(rank_a, rank_b)
            tau_table[severity_a][severity_b] = float(tau_value)
            p_value_table[severity_a][severity_b] = float(p_value)

    formatted_table: dict[str, dict[str, str]] = {}
    for severity in severity_order:
        formatted_table[severity] = {}
        for other in severity_order:
            tau_value = tau_table[severity][other]
            p_value = p_value_table[severity][other]
            tau_str = "nan" if _is_nan(tau_value) else f"{tau_value:.3f}"
            p_str = "nan" if _is_nan(p_value) else f"{p_value:.3f}"
            formatted_table[severity][other] = f"{tau_str} ({p_str})"

    return tau_table, p_value_table, formatted_table


class Rq3InferentialAnalyzer:
    @property
    def outcomes_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3_outcomes"

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3_inferential"

    @property
    def project_root(self) -> Path:
        return settings.artifacts_dir.parent

    @property
    def sk_esd_runner_path(self) -> Path:
        return self.project_root / "scripts" / "analysis" / "rq3_sk_esd_docker_runner.R"

    def run(
        self,
        fixer_policy: FixerAttributionPolicy,
        docker_image: str = "rocker/r2u:24.04",
        run_sk_esd: bool = True,
    ) -> dict[str, Path]:
        output_dir = self.output_root / fixer_policy.value
        sk_esd_dir = output_dir / "sk_esd"
        output_dir.mkdir(parents=True, exist_ok=True)
        sk_esd_dir.mkdir(parents=True, exist_ok=True)

        output_paths: dict[str, Path] = {}
        for metric_name in METRIC_ORDER:
            mean_path, input_paths, ranking_order = self._write_mean_rankings_and_sk_inputs(
                fixer_policy=fixer_policy,
                metric_name=metric_name,
                output_dir=output_dir,
                sk_esd_dir=sk_esd_dir,
            )
            output_paths[f"mean_ranking_{metric_name}"] = mean_path
            for severity, input_path in input_paths.items():
                output_paths[f"sk_esd_input_{metric_name}_{severity}"] = input_path

            tau_table, p_table, formatted_table = compute_kendall_tables(ranking_order)
            tau_path = output_dir / f"kendall_tau_{metric_name}.csv"
            p_path = output_dir / f"kendall_tau_p_values_{metric_name}.csv"
            formatted_path = output_dir / f"kendall_tau_formatted_{metric_name}.csv"
            self._write_matrix_table(tau_path, tau_table)
            self._write_matrix_table(p_path, p_table)
            self._write_string_matrix_table(formatted_path, formatted_table)
            output_paths[f"kendall_tau_{metric_name}"] = tau_path
            output_paths[f"kendall_tau_p_values_{metric_name}"] = p_path
            output_paths[f"kendall_tau_formatted_{metric_name}"] = formatted_path

        if run_sk_esd:
            if not self.sk_esd_runner_path.exists():
                raise FileNotFoundError(
                    f"Missing SK-ESD R runner script: {self.sk_esd_runner_path}"
                )
            self._run_sk_esd_docker(
                fixer_policy=fixer_policy,
                docker_image=docker_image,
                sk_esd_dir=sk_esd_dir,
            )
            for metric_name in METRIC_ORDER:
                for severity in VALID_PRIORITIES:
                    ranking_path = sk_esd_dir / f"sk_esd_ranking_{metric_name}_{severity}.csv"
                    output_paths[f"sk_esd_ranking_{metric_name}_{severity}"] = ranking_path

        logger.info(
            "Generated RQ3 inferential outputs",
            fixer=fixer_policy.value,
            output_dir=str(output_dir),
            run_sk_esd=run_sk_esd,
        )
        return output_paths

    def _write_mean_rankings_and_sk_inputs(
        self,
        fixer_policy: FixerAttributionPolicy,
        metric_name: str,
        output_dir: Path,
        sk_esd_dir: Path,
    ) -> tuple[Path, dict[str, Path], dict[str, list[str]]]:
        mean_path = output_dir / f"mean_ranking_{metric_name}.csv"
        input_paths: dict[str, Path] = {}
        ranking_order: dict[str, list[str]] = {}

        with mean_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "metric",
                    "severity",
                    "rank",
                    "hero_code",
                    "mean_value",
                    "common_project_count",
                ]
            )

            for severity in VALID_PRIORITIES:
                metric_by_hero = self._load_metric_by_hero(
                    fixer_policy=fixer_policy,
                    severity=severity,
                    metric_name=metric_name,
                )
                input_matrix = build_input_matrix(metric_by_hero)
                input_path = sk_esd_dir / f"sk_esd_input_{metric_name}_{severity}.csv"
                self._write_input_matrix_csv(input_path, input_matrix)
                input_paths[severity] = input_path

                ranking_rows = compute_mean_ranking(input_matrix, metric_name=metric_name)
                ranking_order[severity] = [hero_code for _, hero_code, _ in ranking_rows]
                for rank, hero_code, mean_value in ranking_rows:
                    writer.writerow(
                        [
                            metric_name,
                            severity,
                            rank,
                            hero_code,
                            mean_value,
                            len(input_matrix.project_names),
                        ]
                    )

        return mean_path, input_paths, ranking_order

    def _load_metric_by_hero(
        self,
        fixer_policy: FixerAttributionPolicy,
        severity: str,
        metric_name: str,
    ) -> dict[str, dict[str, float]]:
        if metric_name not in METRIC_ORDER:
            raise ValueError(f"Unsupported metric: {metric_name}")

        outcome_path = self.outcomes_root / fixer_policy.value / f"{severity}.csv"
        metric_by_hero: dict[str, dict[str, float]] = {}
        if not outcome_path.exists():
            logger.warning(
                "Missing outcome CSV while generating inferential outputs",
                fixer=fixer_policy.value,
                severity=severity,
                path=str(outcome_path),
            )
            return metric_by_hero

        with outcome_path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                project_name = str(row.get("project_name", "")).strip().lower()
                hero_code = str(row.get("hero_code", "")).strip()
                if not project_name or not hero_code:
                    continue

                n_assigned = int(row.get("n_assigned", "0"))
                if n_assigned <= 0:
                    continue

                value = _parse_float(str(row.get(metric_name, "nan")))
                if _is_nan(value):
                    continue

                metric_by_hero.setdefault(hero_code, {})[project_name] = value

        return metric_by_hero

    @staticmethod
    def _write_input_matrix_csv(output_path: Path, input_matrix: InputMatrix) -> None:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(list(input_matrix.hero_codes))
            for row in input_matrix.rows:
                writer.writerow(list(row))

    @staticmethod
    def _write_matrix_table(output_path: Path, table: dict[str, dict[str, float]]) -> None:
        labels = list(VALID_PRIORITIES)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["severity", *labels])
            for row_label in labels:
                writer.writerow([row_label, *[table[row_label][col_label] for col_label in labels]])

    @staticmethod
    def _write_string_matrix_table(output_path: Path, table: dict[str, dict[str, str]]) -> None:
        labels = list(VALID_PRIORITIES)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["severity", *labels])
            for row_label in labels:
                writer.writerow([row_label, *[table[row_label][col_label] for col_label in labels]])

    def _run_sk_esd_docker(
        self,
        fixer_policy: FixerAttributionPolicy,
        docker_image: str,
        sk_esd_dir: Path,
    ) -> None:
        project_root = self.project_root.resolve()
        input_dir_rel = sk_esd_dir.relative_to(project_root)
        runner_rel = self.sk_esd_runner_path.relative_to(project_root)

        command = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{project_root}:/work",
            "-w",
            "/work",
            docker_image,
            "Rscript",
            runner_rel.as_posix(),
            input_dir_rel.as_posix(),
            input_dir_rel.as_posix(),
        ]
        logger.info(
            "Running SK-ESD Docker command",
            fixer=fixer_policy.value,
            docker_image=docker_image,
            command=" ".join(command),
        )
        subprocess.run(command, check=True)
