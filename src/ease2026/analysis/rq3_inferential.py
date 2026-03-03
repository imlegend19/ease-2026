"""Inferential RQ3 outputs: mean rankings, rank correlations, and Scott-Knott ESD."""

from __future__ import annotations

import csv
import itertools
import math
import random
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scipy.stats import kendalltau, spearmanr

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
RBO_PERSISTENCE: float = 0.90
RBO_PERMUTATION_SAMPLES: int = 10_000
RBO_PERMUTATION_SEED: int = 20260303


@dataclass(frozen=True, slots=True)
class InputMatrix:
    hero_codes: tuple[str, ...]
    project_names: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class Rank1JaccardRow:
    severity_a: str
    severity_b: str
    rank1_categories_a: str
    rank1_categories_b: str
    rank1_intersection_categories: str
    rank1_count_a: int
    rank1_count_b: int
    intersection_count: int
    union_count: int
    jaccard_overlap: float


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
    return _compute_rank_correlation_tables(
        ranking_order_by_severity=ranking_order_by_severity,
        severity_order=severity_order,
        correlation_fn=_kendall_correlation,
    )


def compute_spearman_tables(
    ranking_order_by_severity: dict[str, list[str]],
    severity_order: tuple[str, ...] = VALID_PRIORITIES,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, str]]]:
    """Compute Spearman rho and p-value matrices across severities."""
    return _compute_rank_correlation_tables(
        ranking_order_by_severity=ranking_order_by_severity,
        severity_order=severity_order,
        correlation_fn=_spearman_correlation,
    )


def compute_rbo_tables(
    ranking_order_by_severity: dict[str, list[str]],
    severity_order: tuple[str, ...] = VALID_PRIORITIES,
    persistence: float = RBO_PERSISTENCE,
    permutation_samples: int = RBO_PERMUTATION_SAMPLES,
    permutation_seed: int = RBO_PERMUTATION_SEED,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, str]]]:
    """Compute Rank-Biased Overlap (RBO) matrices across severities with permutation p-values."""
    if not 0.0 < persistence < 1.0:
        raise ValueError("RBO persistence must be between 0 and 1 (exclusive).")
    if permutation_samples <= 0:
        raise ValueError("RBO permutation samples must be a positive integer.")

    rbo_table: dict[str, dict[str, float]] = {
        severity: {other: float("nan") for other in severity_order} for severity in severity_order
    }
    p_value_table: dict[str, dict[str, float]] = {
        severity: {other: float("nan") for other in severity_order} for severity in severity_order
    }

    rng = random.Random(permutation_seed)
    for index_a, severity_a in enumerate(severity_order):
        for index_b, severity_b in enumerate(severity_order):
            if severity_a == severity_b:
                rbo_table[severity_a][severity_b] = 1.0
                p_value_table[severity_a][severity_b] = 0.0
                continue
            if index_b < index_a:
                rbo_table[severity_a][severity_b] = rbo_table[severity_b][severity_a]
                p_value_table[severity_a][severity_b] = p_value_table[severity_b][severity_a]
                continue

            order_a = ranking_order_by_severity.get(severity_a, [])
            order_b = ranking_order_by_severity.get(severity_b, [])
            if not order_a or not order_b:
                continue

            order_b_set = set(order_b)
            common_order_a = [hero_code for hero_code in order_a if hero_code in order_b_set]
            if not common_order_a:
                continue
            common_set = set(common_order_a)
            common_order_b = [hero_code for hero_code in order_b if hero_code in common_set]

            rbo_value = _rbo_extrapolated(common_order_a, common_order_b, persistence)
            p_value = _rbo_permutation_p_value(
                order_a=common_order_a,
                order_b=common_order_b,
                persistence=persistence,
                permutation_samples=permutation_samples,
                rng=rng,
            )
            rbo_table[severity_a][severity_b] = rbo_value
            p_value_table[severity_a][severity_b] = p_value
            rbo_table[severity_b][severity_a] = rbo_value
            p_value_table[severity_b][severity_a] = p_value

    formatted_table: dict[str, dict[str, str]] = {}
    for severity in severity_order:
        formatted_table[severity] = {}
        for other in severity_order:
            rbo_value = rbo_table[severity][other]
            p_value = p_value_table[severity][other]
            rbo_str = "nan" if _is_nan(rbo_value) else f"{rbo_value:.3f}"
            p_str = "nan" if _is_nan(p_value) else f"{p_value:.3f}"
            formatted_table[severity][other] = f"{rbo_str} ({p_str})"

    return rbo_table, p_value_table, formatted_table


def compute_rank1_jaccard_rows(
    rank1_by_severity: dict[str, set[str]],
    severity_order: tuple[str, ...] = VALID_PRIORITIES,
) -> list[Rank1JaccardRow]:
    """Compute pairwise Jaccard overlap of rank-1 SK categories across severities."""
    rows: list[Rank1JaccardRow] = []
    for index_a, severity_a in enumerate(severity_order):
        categories_a = set(rank1_by_severity.get(severity_a, set()))
        for severity_b in severity_order[index_a + 1 :]:
            categories_b = set(rank1_by_severity.get(severity_b, set()))
            intersection = categories_a.intersection(categories_b)
            union = categories_a.union(categories_b)
            jaccard = float("nan") if not union else len(intersection) / len(union)
            rows.append(
                Rank1JaccardRow(
                    severity_a=severity_a,
                    severity_b=severity_b,
                    rank1_categories_a=";".join(sorted(categories_a)),
                    rank1_categories_b=";".join(sorted(categories_b)),
                    rank1_intersection_categories=";".join(sorted(intersection)),
                    rank1_count_a=len(categories_a),
                    rank1_count_b=len(categories_b),
                    intersection_count=len(intersection),
                    union_count=len(union),
                    jaccard_overlap=jaccard,
                )
            )
    return rows


def _kendall_correlation(rank_a: list[int], rank_b: list[int]) -> tuple[float, float]:
    tau_value, p_value = kendalltau(rank_a, rank_b)
    return float(tau_value), float(p_value)


def _spearman_correlation(rank_a: list[int], rank_b: list[int]) -> tuple[float, float]:
    rho_value, p_value = spearmanr(rank_a, rank_b)
    return float(rho_value), float(p_value)


def _rbo_extrapolated(order_a: list[str], order_b: list[str], persistence: float) -> float:
    depth = min(len(order_a), len(order_b))
    if depth <= 0:
        return float("nan")

    seen_a: set[str] = set()
    seen_b: set[str] = set()
    overlap = 0
    weighted_overlap_sum = 0.0

    for d in range(1, depth + 1):
        seen_a.add(order_a[d - 1])
        seen_b.add(order_b[d - 1])
        overlap = len(seen_a.intersection(seen_b))
        agreement_at_depth = overlap / d
        weighted_overlap_sum += agreement_at_depth * (persistence**d)

    agreement_at_depth_k = overlap / depth
    return ((1.0 - persistence) / persistence) * weighted_overlap_sum + (
        agreement_at_depth_k * (persistence**depth)
    )


def _rbo_permutation_p_value(
    order_a: list[str],
    order_b: list[str],
    persistence: float,
    permutation_samples: int,
    rng: random.Random,
) -> float:
    observed = _rbo_extrapolated(order_a, order_b, persistence)
    if _is_nan(observed):
        return float("nan")

    depth = min(len(order_a), len(order_b))
    if depth <= 1:
        return 1.0

    # Use exact enumeration when feasible for deterministic, unbiased p-values.
    if depth <= 8:
        extreme = 0
        total = 0
        for permuted in itertools.permutations(order_b, depth):
            total += 1
            permuted_value = _rbo_extrapolated(order_a, list(permuted), persistence)
            if permuted_value >= observed - 1e-12:
                extreme += 1
        return float(extreme) / float(total) if total > 0 else float("nan")

    extreme = 0
    for _ in range(permutation_samples):
        permuted = rng.sample(order_b, k=depth)
        permuted_value = _rbo_extrapolated(order_a, permuted, persistence)
        if permuted_value >= observed - 1e-12:
            extreme += 1

    # Add-one correction prevents exact zeros with finite Monte Carlo sampling.
    return float(extreme + 1) / float(permutation_samples + 1)


def _compute_rank_correlation_tables(
    ranking_order_by_severity: dict[str, list[str]],
    severity_order: tuple[str, ...],
    correlation_fn: Callable[[list[int], list[int]], tuple[float, float]],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, str]]]:
    coefficient_table: dict[str, dict[str, float]] = {
        severity: {other: float("nan") for other in severity_order} for severity in severity_order
    }
    p_value_table: dict[str, dict[str, float]] = {
        severity: {other: float("nan") for other in severity_order} for severity in severity_order
    }

    for severity_a in severity_order:
        for severity_b in severity_order:
            if severity_a == severity_b:
                coefficient_table[severity_a][severity_b] = 1.0
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
            coefficient_value, p_value = correlation_fn(rank_a, rank_b)
            coefficient_table[severity_a][severity_b] = coefficient_value
            p_value_table[severity_a][severity_b] = p_value

    formatted_table: dict[str, dict[str, str]] = {}
    for severity in severity_order:
        formatted_table[severity] = {}
        for other in severity_order:
            coefficient_value = coefficient_table[severity][other]
            p_value = p_value_table[severity][other]
            coefficient_str = "nan" if _is_nan(coefficient_value) else f"{coefficient_value:.3f}"
            p_str = "nan" if _is_nan(p_value) else f"{p_value:.3f}"
            formatted_table[severity][other] = f"{coefficient_str} ({p_str})"

    return coefficient_table, p_value_table, formatted_table


class Rq3InferentialAnalyzer:
    @property
    def outcomes_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3_outcomes"

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3_inferential"

    @property
    def project_root(self) -> Path:
        return settings.experiment_root

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

            rho_table, rho_p_table, rho_formatted_table = compute_spearman_tables(ranking_order)
            rho_path = output_dir / f"spearman_rho_{metric_name}.csv"
            rho_p_path = output_dir / f"spearman_rho_p_values_{metric_name}.csv"
            rho_formatted_path = output_dir / f"spearman_rho_formatted_{metric_name}.csv"
            self._write_matrix_table(rho_path, rho_table)
            self._write_matrix_table(rho_p_path, rho_p_table)
            self._write_string_matrix_table(rho_formatted_path, rho_formatted_table)
            output_paths[f"spearman_rho_{metric_name}"] = rho_path
            output_paths[f"spearman_rho_p_values_{metric_name}"] = rho_p_path
            output_paths[f"spearman_rho_formatted_{metric_name}"] = rho_formatted_path

            rbo_table, rbo_p_table, rbo_formatted_table = compute_rbo_tables(
                ranking_order_by_severity=ranking_order,
                persistence=RBO_PERSISTENCE,
            )
            rbo_path = output_dir / f"rbo_{metric_name}.csv"
            rbo_p_path = output_dir / f"rbo_p_values_{metric_name}.csv"
            rbo_formatted_path = output_dir / f"rbo_formatted_{metric_name}.csv"
            self._write_matrix_table(rbo_path, rbo_table)
            self._write_matrix_table(rbo_p_path, rbo_p_table)
            self._write_string_matrix_table(rbo_formatted_path, rbo_formatted_table)
            output_paths[f"rbo_{metric_name}"] = rbo_path
            output_paths[f"rbo_p_values_{metric_name}"] = rbo_p_path
            output_paths[f"rbo_formatted_{metric_name}"] = rbo_formatted_path

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
            ranking_table_path = self._write_sk_esd_ranking_table(
                fixer_policy=fixer_policy,
                output_dir=output_dir,
                sk_esd_dir=sk_esd_dir,
            )
            output_paths["rq3_sk_esd_ranking_table"] = ranking_table_path
            if fixer_policy == FixerAttributionPolicy.ASSIGNEE:
                rank1_by_severity = self._load_rank1_sk_categories_by_severity(
                    sk_esd_dir=sk_esd_dir,
                    metric_name="reopen_rate",
                )
                rank1_rows = compute_rank1_jaccard_rows(rank1_by_severity)
                rank1_path = output_dir / "sk_rank1_jaccard_reopen_rate.csv"
                self._write_rank1_jaccard_table(rank1_path, rank1_rows)
                output_paths["sk_rank1_jaccard_reopen_rate"] = rank1_path

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

    @staticmethod
    def _load_rank1_sk_categories_by_severity(
        sk_esd_dir: Path,
        metric_name: str,
    ) -> dict[str, set[str]]:
        rank1_by_severity: dict[str, set[str]] = {severity: set() for severity in VALID_PRIORITIES}
        for severity in VALID_PRIORITIES:
            ranking_path = sk_esd_dir / f"sk_esd_ranking_{metric_name}_{severity}.csv"
            if not ranking_path.exists():
                logger.warning(
                    "Missing SK-ESD ranking CSV while computing rank-1 Jaccard overlap",
                    severity=severity,
                    metric=metric_name,
                    path=str(ranking_path),
                )
                continue

            with ranking_path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    hero_code = str(row.get("hero_code", "")).strip()
                    if not hero_code:
                        continue
                    rank_value = _parse_float(str(row.get("rank", "nan")))
                    if _is_nan(rank_value):
                        continue
                    if math.isclose(rank_value, 1.0, rel_tol=0.0, abs_tol=1e-12):
                        rank1_by_severity[severity].add(hero_code)

        return rank1_by_severity

    @staticmethod
    def _write_rank1_jaccard_table(output_path: Path, rows: list[Rank1JaccardRow]) -> None:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "metric",
                    "severity_a",
                    "severity_b",
                    "rank1_count_a",
                    "rank1_count_b",
                    "intersection_count",
                    "union_count",
                    "jaccard_overlap",
                    "rank1_categories_a",
                    "rank1_categories_b",
                    "rank1_intersection_categories",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        "reopen_rate",
                        row.severity_a,
                        row.severity_b,
                        row.rank1_count_a,
                        row.rank1_count_b,
                        row.intersection_count,
                        row.union_count,
                        row.jaccard_overlap,
                        row.rank1_categories_a,
                        row.rank1_categories_b,
                        row.rank1_intersection_categories,
                    ]
                )

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

    def _write_sk_esd_ranking_table(
        self,
        fixer_policy: FixerAttributionPolicy,
        output_dir: Path,
        sk_esd_dir: Path,
    ) -> Path:
        table_path = output_dir / "rq3_sk_esd_ranking_table.tex"
        ranking_by_cell: dict[tuple[str, str], dict[int, list[str]]] = {}
        fallback_cells: set[tuple[str, str]] = set()
        max_rank = 0

        for severity in VALID_PRIORITIES:
            for metric_name in METRIC_ORDER:
                ranking_path = sk_esd_dir / f"sk_esd_ranking_{metric_name}_{severity}.csv"
                if not ranking_path.exists():
                    fallback_cells.add((severity, metric_name))
                    continue

                with ranking_path.open("r", newline="", encoding="utf-8") as file:
                    rows = list(csv.DictReader(file))
                methods = {str(row.get("method", "")).strip() for row in rows}
                if methods != {"sk_esd_docker"}:
                    fallback_cells.add((severity, metric_name))
                    continue

                ranks: dict[int, list[str]] = {}
                for row in rows:
                    hero_code = str(row.get("hero_code", "")).strip()
                    if not hero_code:
                        continue
                    rank_raw = str(row.get("rank", "")).strip()
                    if not rank_raw:
                        continue
                    try:
                        rank_value = int(rank_raw)
                    except ValueError:
                        continue
                    ranks.setdefault(rank_value, []).append(hero_code)

                if not ranks:
                    fallback_cells.add((severity, metric_name))
                    continue

                ranking_by_cell[(severity, metric_name)] = ranks
                max_rank = max(max_rank, max(ranks))

        if max_rank <= 0:
            max_rank = 1

        def format_rank_entry(hero_codes: list[str]) -> str:
            if not hero_codes:
                return "-"
            if len(hero_codes) <= 4:
                return ", ".join(hero_codes)
            chunks = [", ".join(hero_codes[i : i + 4]) for i in range(0, len(hero_codes), 4)]
            return "\\begin{tabular}[c]{@{}c@{}}" + " \\\\ ".join(chunks) + "\\end{tabular}"

        severity_labels = {
            "trivial": "Trivial",
            "minor": "Minor",
            "major": "Major",
            "critical": "Critical",
            "blocker": "Blocker",
        }
        metric_labels = {
            "fix_rate": "Fixed",
            "reopen_rate": "Reopened",
        }
        fixer_labels = {
            FixerAttributionPolicy.ASSIGNEE: "assignee",
            FixerAttributionPolicy.ASSIGNEE_AT_FIX_TIME: "assignee-at-fix-time",
            FixerAttributionPolicy.COMMIT_AUTHOR: "commit-author",
        }
        label_suffix = fixer_labels[fixer_policy]
        dataset_label = settings.dataset_name.replace("_", "\\_")

        lines: list[str] = [
            "\\begin{table*}[htbp]",
            "    \\centering",
            "    \\scriptsize",
            f"    \\caption{{Ranking of hero categories by Scott-Knott ESD (RQ3, {label_suffix} policy, {dataset_label})}}",
            f"    \\label{{tab:rq3-herorank-{label_suffix}}}",
            "    \\begin{adjustbox}{max width=\\textwidth}",
            "        \\begin{tabular}{|c|cc|cc|cc|cc|cc|}",
            "            \\hline",
            (
                "            \\multirow{2}{*}{\\textit{\\textbf{Ranks}}} "
                "& \\multicolumn{2}{c|}{\\textit{\\textbf{Trivial}}} "
                "& \\multicolumn{2}{c|}{\\textit{\\textbf{Minor}}} "
                "& \\multicolumn{2}{c|}{\\textit{\\textbf{Major}}} "
                "& \\multicolumn{2}{c|}{\\textit{\\textbf{Critical}}} "
                "& \\multicolumn{2}{c|}{\\textit{\\textbf{Blocker}}} \\\\ \\cline{2-11}"
            ),
            (
                "            & \\multicolumn{1}{c|}{\\textit{\\textbf{Fixed}}} "
                "& \\textit{\\textbf{Reopened}} "
                "& \\multicolumn{1}{c|}{\\textit{\\textbf{Fixed}}} "
                "& \\textit{\\textbf{Reopened}} "
                "& \\multicolumn{1}{c|}{\\textit{\\textbf{Fixed}}} "
                "& \\textit{\\textbf{Reopened}} "
                "& \\multicolumn{1}{c|}{\\textit{\\textbf{Fixed}}} "
                "& \\textit{\\textbf{Reopened}} "
                "& \\multicolumn{1}{c|}{\\textit{\\textbf{Fixed}}} "
                "& \\textit{\\textbf{Reopened}} \\\\ \\hline"
            ),
        ]

        for rank in range(1, max_rank + 1):
            row_entries: list[str] = []
            for severity in VALID_PRIORITIES:
                for metric_name in METRIC_ORDER:
                    cell_key = (severity, metric_name)
                    if cell_key in fallback_cells:
                        row_entries.append("N/A\\textsuperscript{\\dagger}")
                        continue
                    cell_ranks = ranking_by_cell.get(cell_key, {})
                    hero_codes = cell_ranks.get(rank, [])
                    row_entries.append(format_rank_entry(hero_codes))
            lines.append(
                f"            \\textit{{\\textbf{{{rank}}}}} & "
                + " & ".join(row_entries)
                + " \\\\ \\hline"
            )

        lines.append("        \\end{tabular}")
        lines.append("    \\end{adjustbox}")
        if fallback_cells:
            fallback_details = []
            for severity in VALID_PRIORITIES:
                for metric_name in METRIC_ORDER:
                    if (severity, metric_name) in fallback_cells:
                        fallback_details.append(
                            f"{severity_labels[severity]}/{metric_labels[metric_name]}"
                        )
            lines.append(
                "    {\\footnotesize\\textsuperscript{\\dagger}N/A (fallback): "
                "non-SK results detected (method != sk\\_esd\\_docker) for "
                + ", ".join(fallback_details)
                + ".}"
            )
        lines.append("\\end{table*}")

        table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return table_path
