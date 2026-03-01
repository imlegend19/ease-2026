"""Generate publication-ready figures for EASE 2026 RQs."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from ease2026.analysis.rq1 import HERO_TYPE_ORDER
from ease2026.core.logging import get_logger
from ease2026.core.settings import settings
from ease2026.outcomes.definitions import VALID_PRIORITIES

logger = get_logger(__name__)

SEVERITY_ORDER: tuple[str, ...] = VALID_PRIORITIES
HERO_TYPE_LABELS: dict[str, str] = {
    "technical": "Technical",
    "social": "Social",
    "sociotechnical": "Sociotechnical",
    "technosocial": "Technosocial",
    "super": "Super",
}
HERO_TYPE_COLORS: dict[str, str] = {
    "technical": "#33658A",
    "social": "#2F855A",
    "sociotechnical": "#DD6B20",
    "technosocial": "#B83280",
    "super": "#4A5568",
}

RQ1_BASE_METRIC_ORDER: tuple[str, ...] = ("T1", "T2", "T3", "S1", "S2")
RQ1_METRIC_TO_DIMENSION: dict[str, str] = {
    "T1": "technical",
    "T2": "technical",
    "T3": "technical",
    "S1": "social",
    "S2": "social",
}
RQ1_DIMENSION_COLORS: dict[str, str] = {
    "technical": "#4C78A8",
    "social": "#E15759",
}


@dataclass(frozen=True, slots=True)
class Rq3Cell:
    median: float
    iqr: float
    n_projects_with_assigned: int


@dataclass(frozen=True, slots=True)
class Rq1MetricSummary:
    minimum: float
    q1: float
    median: float
    q3: float
    maximum: float


def _is_nan(value: float) -> bool:
    return math.isnan(value)


def summarize_rq1_threshold_prevalence(
    rows: list[dict[str, float | str]],
    metric_order: tuple[str, ...] = RQ1_BASE_METRIC_ORDER,
) -> dict[str, Rq1MetricSummary]:
    """Summarize threshold prevalence with dedupe by (top_fraction, coverage_fraction)."""
    by_metric_and_ratio: dict[str, dict[tuple[float, float], float]] = {
        metric_code: {} for metric_code in metric_order
    }
    for row in rows:
        metric_code = str(row["metric_code"])
        if metric_code not in by_metric_and_ratio:
            continue
        ratio_key = (float(row["top_fraction"]), float(row["coverage_fraction"]))
        by_metric_and_ratio[metric_code][ratio_key] = float(row["project_prevalence_pct"])

    summary: dict[str, Rq1MetricSummary] = {}
    for metric_code in metric_order:
        values = sorted(by_metric_and_ratio[metric_code].values())
        if not values:
            nan = float("nan")
            summary[metric_code] = Rq1MetricSummary(nan, nan, nan, nan, nan)
            continue
        summary[metric_code] = Rq1MetricSummary(
            minimum=float(values[0]),
            q1=float(np.quantile(values, 0.25)),
            median=float(np.quantile(values, 0.5)),
            q3=float(np.quantile(values, 0.75)),
            maximum=float(values[-1]),
        )

    return summary


def build_type_overlap_matrix(
    rows: list[dict[str, str]],
    hero_type_order: tuple[str, ...] = HERO_TYPE_ORDER,
) -> np.ndarray:
    """Build a symmetric 5x5 overlap matrix from pairwise overlap rows."""
    index_by_type = {hero_type: index for index, hero_type in enumerate(hero_type_order)}
    matrix = np.full((len(hero_type_order), len(hero_type_order)), np.nan, dtype=float)
    np.fill_diagonal(matrix, 1.0)

    for row in rows:
        group_a = row.get("group_a", "").strip()
        group_b = row.get("group_b", "").strip()
        if group_a not in index_by_type or group_b not in index_by_type:
            continue
        value = float(row["pair_jaccard"])
        idx_a = index_by_type[group_a]
        idx_b = index_by_type[group_b]
        matrix[idx_a, idx_b] = value
        matrix[idx_b, idx_a] = value

    return matrix


def build_rq3_effect_grids(
    rows: list[dict[str, str]],
    fixer: str = "assignee",
    hero_type_order: tuple[str, ...] = HERO_TYPE_ORDER,
    severity_order: tuple[str, ...] = SEVERITY_ORDER,
) -> tuple[np.ndarray, np.ndarray, list[list[str]], list[list[str]]]:
    """Build delta-vs-technical median grids for fix and reopen outcomes."""
    data: dict[tuple[str, str], Rq3Cell] = {}
    for row in rows:
        if row.get("fixer", "").strip() != fixer:
            continue
        hero_type = row.get("hero_type", "").strip()
        severity = row.get("severity", "").strip()
        if hero_type not in hero_type_order or severity not in severity_order:
            continue

        fix_median = float(row["fix_rate_median"])
        fix_iqr = float(row["fix_rate_iqr"])
        reopen_median = float(row["reopen_rate_median"])
        reopen_iqr = float(row["reopen_rate_iqr"])
        n_projects = int(row["n_projects_with_assigned"])

        data[(hero_type, severity, "fix")] = Rq3Cell(
            median=fix_median,
            iqr=fix_iqr,
            n_projects_with_assigned=n_projects,
        )
        data[(hero_type, severity, "reopen")] = Rq3Cell(
            median=reopen_median,
            iqr=reopen_iqr,
            n_projects_with_assigned=n_projects,
        )

    fix_delta = np.full((len(hero_type_order), len(severity_order)), np.nan, dtype=float)
    reopen_delta = np.full((len(hero_type_order), len(severity_order)), np.nan, dtype=float)
    fix_annotations = [["" for _ in severity_order] for _ in hero_type_order]
    reopen_annotations = [["" for _ in severity_order] for _ in hero_type_order]

    for severity_index, severity in enumerate(severity_order):
        fix_baseline = data.get(("technical", severity, "fix"))
        reopen_baseline = data.get(("technical", severity, "reopen"))
        fix_baseline_value = fix_baseline.median if fix_baseline is not None else float("nan")
        reopen_baseline_value = (
            reopen_baseline.median if reopen_baseline is not None else float("nan")
        )

        for hero_index, hero_type in enumerate(hero_type_order):
            fix_cell = data.get((hero_type, severity, "fix"))
            if fix_cell is not None and not _is_nan(fix_baseline_value):
                fix_delta[hero_index, severity_index] = fix_cell.median - fix_baseline_value
                fix_annotations[hero_index][severity_index] = (
                    f"{fix_cell.median:.1f}\nIQR {fix_cell.iqr:.1f}\nn={fix_cell.n_projects_with_assigned}"
                )

            reopen_cell = data.get((hero_type, severity, "reopen"))
            if reopen_cell is not None and not _is_nan(reopen_baseline_value):
                reopen_delta[hero_index, severity_index] = (
                    reopen_cell.median - reopen_baseline_value
                )
                reopen_annotations[hero_index][severity_index] = (
                    f"{reopen_cell.median:.1f}\nIQR {reopen_cell.iqr:.1f}\nn={reopen_cell.n_projects_with_assigned}"
                )

    return fix_delta, reopen_delta, fix_annotations, reopen_annotations


class FinalFigureGenerator:
    @property
    def final_tables_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "final_tables"

    @property
    def robustness_csv_path(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "robustness" / "threshold_sweep_master.csv"

    @property
    def output_dir(self) -> Path:
        return settings.outputs_plots_dir / "analysis" / "final_figures"

    def run(
        self,
        fixer_for_rq3: str = "assignee",
        dpi: int = 300,
        save_svg: bool = True,
    ) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        outputs: dict[str, Path] = {}

        outputs["figure_1_technical_social"] = self._plot_rq1_technical_social_prevalence(
            dpi=dpi,
            save_svg=save_svg,
        )
        outputs["figure_1_hero_type_appendix"] = self._plot_figure_1_prevalence(
            dpi=dpi,
            save_svg=save_svg,
        )
        if self.robustness_csv_path.exists():
            (
                threshold_figure_path,
                baseline_csv_path,
                threshold_long_csv_path,
                threshold_summary_csv_path,
            ) = self._plot_rq1_technical_social_threshold_ranges(dpi=dpi, save_svg=save_svg)
            outputs["figure_1_technical_social_threshold_ranges"] = threshold_figure_path
            outputs["rq1_tikz_baseline_csv"] = baseline_csv_path
            outputs["rq1_tikz_threshold_long_csv"] = threshold_long_csv_path
            outputs["rq1_tikz_threshold_summary_csv"] = threshold_summary_csv_path
        else:
            logger.warning(
                "Skipping RQ1 threshold figure and CSV exports; robustness CSV not found",
                path=str(self.robustness_csv_path),
            )
        outputs["figure_2_overlap"] = self._plot_figure_2_overlap(dpi=dpi, save_svg=save_svg)
        outputs["figure_3_bug_performance"] = self._plot_figure_3_bug_performance(
            fixer=fixer_for_rq3,
            dpi=dpi,
            save_svg=save_svg,
        )

        if self.robustness_csv_path.exists():
            outputs["figure_4_threshold_sensitivity"] = self._plot_figure_4_threshold_sensitivity(
                dpi=dpi,
                save_svg=save_svg,
            )
        else:
            logger.warning(
                "Skipping Figure 4; threshold sweep master CSV not found",
                path=str(self.robustness_csv_path),
            )

        logger.info(
            "Generated final figures",
            output_dir=str(self.output_dir),
            figure_count=len(outputs),
            fixer_for_rq3=fixer_for_rq3,
        )
        return outputs

    def _load_rq1_base_metric_rows(self, csv_path: Path) -> list[dict[str, str]]:
        rows = self._read_csv(csv_path)
        return [row for row in rows if row.get("hero_code", "").strip() in RQ1_BASE_METRIC_ORDER]

    def _load_threshold_base_metric_rows(self) -> list[dict[str, float | str]]:
        rows = self._read_csv(self.robustness_csv_path)
        metric_rows: list[dict[str, float | str]] = []
        for row in rows:
            if row.get("status", "").strip() != "success":
                continue
            run_dir = Path(str(row["run_dir"]))
            prevalence_path = (
                run_dir
                / "outputs"
                / "csv"
                / "analysis"
                / "final_tables"
                / "rq1_base_metric_prevalence.csv"
            )
            if not prevalence_path.exists():
                logger.warning(
                    "Missing run base prevalence CSV for RQ1 threshold figure",
                    run_id=row.get("run_id", ""),
                    path=str(prevalence_path),
                )
                continue
            run_rows = self._load_rq1_base_metric_rows(prevalence_path)
            for run_row in run_rows:
                metric_rows.append(
                    {
                        "run_id": str(row["run_id"]),
                        "top_fraction": float(row["top_fraction"]),
                        "coverage_fraction": float(row["coverage_fraction"]),
                        "hybrid_quantile": float(row["hybrid_quantile"]),
                        "metric_code": str(run_row["hero_code"]),
                        "project_prevalence_pct": float(run_row["project_prevalence_pct"]),
                    }
                )
        return metric_rows

    def _plot_data_dir(self) -> Path:
        directory = self.final_tables_dir / "plot_data"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _write_csv_rows(
        self,
        output_path: Path,
        header: list[str],
        rows: list[list[object]],
    ) -> Path:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(rows)
        return output_path

    def _plot_rq1_technical_social_prevalence(self, dpi: int, save_svg: bool) -> Path:
        base_rows = self._load_rq1_base_metric_rows(
            self.final_tables_dir / "rq1_base_metric_prevalence.csv"
        )
        base_by_metric = {row["hero_code"]: row for row in base_rows}

        prevalences = np.array(
            [
                float(base_by_metric.get(metric_code, {}).get("project_prevalence_pct", "nan"))
                for metric_code in RQ1_BASE_METRIC_ORDER
            ],
            dtype=float,
        )
        x_positions = np.arange(len(RQ1_BASE_METRIC_ORDER))
        colors = [
            RQ1_DIMENSION_COLORS[RQ1_METRIC_TO_DIMENSION[metric_code]]
            for metric_code in RQ1_BASE_METRIC_ORDER
        ]

        figure, axis = plt.subplots(figsize=(10.8, 5.6))
        bars = axis.bar(
            x_positions,
            prevalences,
            color=colors,
            alpha=0.85,
            edgecolor="#1A202C",
            linewidth=0.6,
        )

        axis.set_ylim(0, 100)
        axis.set_ylabel("Percentage of Projects")
        axis.set_xlabel("Technical fronts                                      Social fronts")
        axis.set_xticks(x_positions)
        axis.set_xticklabels(RQ1_BASE_METRIC_ORDER, fontsize=12, fontweight="bold")
        axis.grid(axis="y", alpha=0.22)
        axis.set_axisbelow(True)
        axis.axvline(2.5, color="#4A5568", linestyle="--", linewidth=1.0, alpha=0.7)
        axis.set_title(
            "Figure 1A. Hero-Project Prevalence Across Technical and Social Metrics (20/80)",
            loc="left",
            fontsize=13,
            fontweight="bold",
        )

        for bar, value in zip(bars, prevalences, strict=True):
            if np.isnan(value):
                continue
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                value + 1.0,
                f"{value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10.5,
                fontweight="bold",
            )

        legend_handles = [
            Patch(
                facecolor=RQ1_DIMENSION_COLORS["technical"], edgecolor="#1A202C", label="Technical"
            ),
            Patch(facecolor=RQ1_DIMENSION_COLORS["social"], edgecolor="#1A202C", label="Social"),
        ]
        axis.legend(handles=legend_handles, loc="upper right", frameon=True)
        return self._save_figure(figure, "figure_1a_technical_social_20_80", dpi, save_svg)

    def _plot_rq1_technical_social_threshold_ranges(
        self,
        dpi: int,
        save_svg: bool,
    ) -> tuple[Path, Path, Path, Path]:
        base_rows = self._load_rq1_base_metric_rows(
            self.final_tables_dir / "rq1_base_metric_prevalence.csv"
        )
        threshold_rows = self._load_threshold_base_metric_rows()
        if not threshold_rows:
            raise ValueError("No threshold rows available for RQ1 technical/social ranges.")

        base_by_metric = {row["hero_code"]: row for row in base_rows}
        baseline_values = {
            metric_code: float(base_by_metric[metric_code]["project_prevalence_pct"])
            for metric_code in RQ1_BASE_METRIC_ORDER
            if metric_code in base_by_metric
        }
        summary_by_metric = summarize_rq1_threshold_prevalence(threshold_rows)

        plot_data_dir = self._plot_data_dir()
        baseline_csv_path = self._write_csv_rows(
            plot_data_dir / "rq1_technical_social_baseline.csv",
            [
                "metric_code",
                "dimension",
                "project_prevalence_pct",
                "project_count_hero",
                "project_count_total",
            ],
            [
                [
                    metric_code,
                    RQ1_METRIC_TO_DIMENSION[metric_code],
                    baseline_values.get(metric_code, float("nan")),
                    int(base_by_metric[metric_code]["project_count_hero"]),
                    int(base_by_metric[metric_code]["project_count_total"]),
                ]
                for metric_code in RQ1_BASE_METRIC_ORDER
                if metric_code in base_by_metric
            ],
        )
        threshold_long_csv_path = self._write_csv_rows(
            plot_data_dir / "rq1_technical_social_threshold_long.csv",
            [
                "run_id",
                "top_fraction",
                "coverage_fraction",
                "hybrid_quantile",
                "metric_code",
                "project_prevalence_pct",
            ],
            [
                [
                    str(row["run_id"]),
                    float(row["top_fraction"]),
                    float(row["coverage_fraction"]),
                    float(row["hybrid_quantile"]),
                    str(row["metric_code"]),
                    float(row["project_prevalence_pct"]),
                ]
                for row in threshold_rows
            ],
        )
        threshold_summary_csv_path = self._write_csv_rows(
            plot_data_dir / "rq1_technical_social_threshold_summary.csv",
            [
                "metric_code",
                "dimension",
                "baseline_prevalence_pct",
                "prevalence_min",
                "prevalence_q1",
                "prevalence_median",
                "prevalence_q3",
                "prevalence_max",
            ],
            [
                [
                    metric_code,
                    RQ1_METRIC_TO_DIMENSION[metric_code],
                    baseline_values.get(metric_code, float("nan")),
                    summary_by_metric[metric_code].minimum,
                    summary_by_metric[metric_code].q1,
                    summary_by_metric[metric_code].median,
                    summary_by_metric[metric_code].q3,
                    summary_by_metric[metric_code].maximum,
                ]
                for metric_code in RQ1_BASE_METRIC_ORDER
            ],
        )

        x_positions = np.arange(len(RQ1_BASE_METRIC_ORDER))
        bar_colors = [
            RQ1_DIMENSION_COLORS[RQ1_METRIC_TO_DIMENSION[metric_code]]
            for metric_code in RQ1_BASE_METRIC_ORDER
        ]
        baseline_series = np.array(
            [
                baseline_values.get(metric_code, float("nan"))
                for metric_code in RQ1_BASE_METRIC_ORDER
            ],
            dtype=float,
        )
        min_series = np.array(
            [summary_by_metric[metric_code].minimum for metric_code in RQ1_BASE_METRIC_ORDER],
            dtype=float,
        )
        median_series = np.array(
            [summary_by_metric[metric_code].median for metric_code in RQ1_BASE_METRIC_ORDER],
            dtype=float,
        )
        max_series = np.array(
            [summary_by_metric[metric_code].maximum for metric_code in RQ1_BASE_METRIC_ORDER],
            dtype=float,
        )

        figure, axis = plt.subplots(figsize=(10.8, 5.8))
        bars = axis.bar(
            x_positions,
            baseline_series,
            color=bar_colors,
            alpha=0.72,
            edgecolor="#1A202C",
            linewidth=0.6,
            label="Baseline (top=0.20, coverage=0.80)",
        )
        axis.vlines(
            x_positions,
            min_series,
            max_series,
            colors="#2D3748",
            linewidth=2.0,
            label="Threshold range (min-max)",
        )
        axis.scatter(
            x_positions,
            median_series,
            marker="D",
            color="#1A202C",
            s=45,
            zorder=3,
            label="Threshold median",
        )

        for bar, baseline, min_value, max_value in zip(
            bars, baseline_series, min_series, max_series, strict=True
        ):
            if np.isnan(baseline):
                continue
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                baseline + 0.9,
                f"{baseline:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9.8,
                fontweight="bold",
            )
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                max_value + 0.8,
                f"{min_value:.1f}-{max_value:.1f}",
                ha="center",
                va="bottom",
                fontsize=8.2,
                color="#2D3748",
            )

        axis.set_ylim(0, 100)
        axis.set_ylabel("Percentage of Projects")
        axis.set_xlabel("Technical fronts                                      Social fronts")
        axis.set_xticks(x_positions)
        axis.set_xticklabels(RQ1_BASE_METRIC_ORDER, fontsize=12, fontweight="bold")
        axis.axvline(2.5, color="#4A5568", linestyle="--", linewidth=1.0, alpha=0.7)
        axis.grid(axis="y", alpha=0.22)
        axis.set_axisbelow(True)
        axis.set_title(
            "Figure 1B. Technical/Social Hero Prevalence Under Alternative Ratios",
            loc="left",
            fontsize=13,
            fontweight="bold",
        )
        axis.legend(loc="upper right", fontsize=8.8, frameon=True)
        axis.text(
            0.01,
            -0.2,
            "Range computed across top_fraction in {0.15,0.20,0.25,0.30} and "
            "coverage_fraction in {0.70,0.80,0.85}.",
            transform=axis.transAxes,
            fontsize=8.8,
            color="#2D3748",
        )

        figure_path = self._save_figure(
            figure,
            "figure_1b_technical_social_threshold_ranges",
            dpi,
            save_svg,
        )
        return figure_path, baseline_csv_path, threshold_long_csv_path, threshold_summary_csv_path

    def _load_threshold_prevalence_rows(self) -> list[dict[str, float | str]]:
        rows = self._read_csv(self.robustness_csv_path)
        prevalence_rows: list[dict[str, float | str]] = []

        for row in rows:
            if row.get("status", "").strip() != "success":
                continue

            run_dir = Path(str(row["run_dir"]))
            prevalence_path = (
                run_dir
                / "outputs"
                / "csv"
                / "analysis"
                / "final_tables"
                / "rq1_hero_type_prevalence.csv"
            )
            if not prevalence_path.exists():
                logger.warning(
                    "Missing run prevalence CSV for threshold figure",
                    run_id=row.get("run_id", ""),
                    path=str(prevalence_path),
                )
                continue

            with prevalence_path.open("r", newline="", encoding="utf-8") as file:
                prevalence_table = list(csv.DictReader(file))
                for prevalence_row in prevalence_table:
                    prevalence_rows.append(
                        {
                            "run_id": str(row["run_id"]),
                            "top_fraction": float(row["top_fraction"]),
                            "coverage_fraction": float(row["coverage_fraction"]),
                            "hybrid_quantile": float(row["hybrid_quantile"]),
                            "hero_type": str(prevalence_row["hero_type"]),
                            "project_prevalence_pct": float(
                                prevalence_row["project_prevalence_pct"]
                            ),
                        }
                    )

        return prevalence_rows

    def _read_csv(self, csv_path: Path) -> list[dict[str, str]]:
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing required CSV: {csv_path}")
        with csv_path.open("r", newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def _save_figure(self, figure: plt.Figure, stem: str, dpi: int, save_svg: bool) -> Path:
        png_path = self.output_dir / f"{stem}.png"
        figure.savefig(png_path, dpi=dpi, bbox_inches="tight")
        if save_svg:
            svg_path = self.output_dir / f"{stem}.svg"
            figure.savefig(svg_path, bbox_inches="tight")
        plt.close(figure)
        return png_path

    def _plot_figure_1_prevalence(self, dpi: int, save_svg: bool) -> Path:
        rows = self._read_csv(self.final_tables_dir / "rq1_hero_type_prevalence.csv")
        rows_by_type = {row["hero_type"]: row for row in rows}

        x_positions = np.arange(len(HERO_TYPE_ORDER))
        prevalences = np.array(
            [
                float(rows_by_type.get(hero_type, {}).get("project_prevalence_pct", "nan"))
                for hero_type in HERO_TYPE_ORDER
            ],
            dtype=float,
        )
        project_counts = np.array(
            [
                int(rows_by_type.get(hero_type, {}).get("project_count_hero_any_metric", "0"))
                for hero_type in HERO_TYPE_ORDER
            ],
            dtype=int,
        )
        project_total = int(rows[0]["project_count_total"]) if rows else 0

        figure, axis = plt.subplots(figsize=(10.5, 5.5))
        bars = axis.bar(
            x_positions,
            prevalences,
            color=[HERO_TYPE_COLORS[hero_type] for hero_type in HERO_TYPE_ORDER],
            alpha=0.92,
            edgecolor="#1A202C",
            linewidth=0.5,
        )
        axis.set_ylim(0, 100)
        axis.set_ylabel("Hero-project prevalence (%)")
        axis.set_title(
            "Figure 1. Prevalence of Hero Projects by Type",
            loc="left",
            fontsize=13,
            fontweight="bold",
        )
        axis.set_xticks(x_positions)
        axis.set_xticklabels([HERO_TYPE_LABELS[hero_type] for hero_type in HERO_TYPE_ORDER])
        axis.grid(axis="y", alpha=0.22)
        axis.set_axisbelow(True)

        for bar, prevalence, count in zip(bars, prevalences, project_counts, strict=True):
            if _is_nan(float(prevalence)):
                continue
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + 1.0,
                f"{prevalence:.1f}%\n({count}/{project_total})",
                ha="center",
                va="bottom",
                fontsize=8.5,
            )

        axis.text(
            0.01,
            -0.22,
            "Multifaceted = Sociotechnical + Technosocial + Super",
            transform=axis.transAxes,
            fontsize=9,
            color="#2D3748",
        )

        return self._save_figure(figure, "figure_1_prevalence_by_hero_type", dpi, save_svg)

    def _plot_figure_1_prevalence_thresholds(self, dpi: int, save_svg: bool) -> Path:
        threshold_rows = self._load_threshold_prevalence_rows()
        if not threshold_rows:
            raise ValueError("No successful threshold prevalence rows found.")

        top_values = sorted({float(row["top_fraction"]) for row in threshold_rows})
        coverage_values = sorted({float(row["coverage_fraction"]) for row in threshold_rows})
        quantile_values = sorted({float(row["hybrid_quantile"]) for row in threshold_rows})
        combos = [
            (coverage, quantile) for coverage in coverage_values for quantile in quantile_values
        ]

        prevalence_lookup: dict[tuple[float, float, float, str], float] = {}
        for row in threshold_rows:
            key = (
                float(row["top_fraction"]),
                float(row["coverage_fraction"]),
                float(row["hybrid_quantile"]),
                str(row["hero_type"]),
            )
            prevalence_lookup[key] = float(row["project_prevalence_pct"])

        color_by_coverage = {
            coverage: color
            for coverage, color in zip(
                coverage_values,
                ("#1F77B4", "#2CA02C", "#FF7F0E"),
                strict=False,
            )
        }
        hatch_by_quantile = {
            quantile: hatch for quantile, hatch in zip(quantile_values, ("", "//"), strict=False)
        }

        columns = min(2, len(top_values))
        rows = math.ceil(len(top_values) / columns)
        figure, axes = plt.subplots(
            nrows=rows,
            ncols=columns,
            figsize=(7.2 * columns, 4.8 * rows),
            constrained_layout=True,
        )
        axes_array = np.atleast_1d(axes).flatten()

        x_positions = np.arange(len(HERO_TYPE_ORDER))
        bar_width = 0.12 if len(combos) >= 6 else 0.18
        combo_offsets = [
            (index - (len(combos) - 1) / 2.0) * bar_width for index, _ in enumerate(combos)
        ]

        for axis, top_fraction in zip(axes_array, top_values, strict=False):
            for (coverage, quantile), offset in zip(combos, combo_offsets, strict=True):
                y_values = [
                    prevalence_lookup.get((top_fraction, coverage, quantile, hero_type), math.nan)
                    for hero_type in HERO_TYPE_ORDER
                ]
                axis.bar(
                    x_positions + offset,
                    y_values,
                    width=bar_width * 0.95,
                    color=color_by_coverage[coverage],
                    hatch=hatch_by_quantile[quantile],
                    edgecolor="#1A202C",
                    linewidth=0.4,
                    alpha=0.9,
                )

            axis.set_title(f"top_fraction = {top_fraction:.2f}", fontsize=11.5, fontweight="bold")
            axis.set_xticks(x_positions)
            axis.set_xticklabels(
                [HERO_TYPE_LABELS[hero_type] for hero_type in HERO_TYPE_ORDER],
                rotation=20,
                ha="right",
            )
            axis.set_ylim(0, 100)
            axis.grid(axis="y", alpha=0.2)
            axis.set_axisbelow(True)
            axis.set_ylabel("Prevalence (%)")

        for axis in axes_array[len(top_values) :]:
            axis.axis("off")

        coverage_handles = [
            Patch(
                facecolor=color_by_coverage[coverage],
                edgecolor="#1A202C",
                label=f"coverage={coverage:.2f}",
            )
            for coverage in coverage_values
        ]
        quantile_handles = [
            Patch(
                facecolor="#FFFFFF",
                edgecolor="#1A202C",
                hatch=hatch_by_quantile[quantile],
                label=f"q={quantile:.2f}",
            )
            for quantile in quantile_values
        ]
        axes_array[0].legend(
            handles=coverage_handles + quantile_handles,
            loc="upper right",
            fontsize=8.5,
            frameon=True,
        )

        figure.suptitle(
            "Figure 1b. Prevalence by Hero Type Across Threshold Ratios",
            fontsize=13,
            fontweight="bold",
            x=0.01,
            ha="left",
        )
        return self._save_figure(
            figure,
            "figure_1_prevalence_threshold_panels",
            dpi,
            save_svg,
        )

    def _plot_figure_2_overlap(self, dpi: int, save_svg: bool) -> Path:
        rows = self._read_csv(self.final_tables_dir / "rq2_overlap_type_groups.csv")
        matrix = build_type_overlap_matrix(rows)

        figure, axis = plt.subplots(figsize=(7.8, 6.6))
        image = axis.imshow(matrix, cmap="YlGnBu", vmin=0.0, vmax=1.0)
        axis.set_title(
            "Figure 2. Hero-Type Overlap Stability (Jaccard)",
            loc="left",
            fontsize=13,
            fontweight="bold",
        )
        labels = [HERO_TYPE_LABELS[hero_type] for hero_type in HERO_TYPE_ORDER]
        axis.set_xticks(np.arange(len(labels)))
        axis.set_yticks(np.arange(len(labels)))
        axis.set_xticklabels(labels, rotation=25, ha="right")
        axis.set_yticklabels(labels)

        for row_index in range(matrix.shape[0]):
            for col_index in range(matrix.shape[1]):
                value = matrix[row_index, col_index]
                if np.isnan(value):
                    text = "NA"
                    text_color = "#111111"
                else:
                    text = f"{value:.2f}"
                    text_color = "white" if value > 0.55 else "#111111"
                axis.text(
                    col_index,
                    row_index,
                    text,
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=text_color,
                )

        colorbar = figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
        colorbar.set_label("Project-author pair Jaccard overlap")
        return self._save_figure(figure, "figure_2_hero_type_overlap_matrix", dpi, save_svg)

    def _plot_figure_3_bug_performance(self, fixer: str, dpi: int, save_svg: bool) -> Path:
        rows = self._read_csv(self.final_tables_dir / "rq3_type_summary.csv")
        fix_delta, reopen_delta, fix_annotations, reopen_annotations = build_rq3_effect_grids(
            rows=rows,
            fixer=fixer,
        )

        max_abs = np.nanmax(
            np.abs(
                np.concatenate(
                    [fix_delta.flatten(), reopen_delta.flatten()],
                    axis=0,
                )
            )
        )
        if _is_nan(float(max_abs)) or max_abs == 0:
            max_abs = 1.0

        figure, axes = plt.subplots(nrows=1, ncols=2, figsize=(15.0, 6.2), constrained_layout=True)
        datasets = (
            ("Fix-rate median delta vs Technical", fix_delta, fix_annotations),
            ("Reopen-rate median delta vs Technical", reopen_delta, reopen_annotations),
        )

        for axis, (title, values, cell_annotations) in zip(axes, datasets, strict=True):
            image = axis.imshow(values, cmap="RdBu_r", vmin=-max_abs, vmax=max_abs)
            axis.set_title(title, fontsize=11, fontweight="bold")
            axis.set_xticks(np.arange(len(SEVERITY_ORDER)))
            axis.set_xticklabels(
                [severity.capitalize() for severity in SEVERITY_ORDER], rotation=20
            )
            axis.set_yticks(np.arange(len(HERO_TYPE_ORDER)))
            axis.set_yticklabels([HERO_TYPE_LABELS[hero_type] for hero_type in HERO_TYPE_ORDER])

            for row_index, hero_type in enumerate(HERO_TYPE_ORDER):
                for col_index, _severity in enumerate(SEVERITY_ORDER):
                    value = values[row_index, col_index]
                    annotation = cell_annotations[row_index][col_index]
                    if np.isnan(value):
                        axis.text(
                            col_index,
                            row_index,
                            "NA",
                            ha="center",
                            va="center",
                            fontsize=8,
                            color="#111111",
                        )
                        continue
                    axis.text(
                        col_index,
                        row_index,
                        f"{value:+.1f}\n{annotation}",
                        ha="center",
                        va="center",
                        fontsize=7.2,
                        color="white" if abs(value) > max_abs * 0.35 else "#111111",
                    )

            colorbar = figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
            colorbar.set_label("Delta percentage points")

        figure.suptitle(
            f"Figure 3. Bug-Fixing Performance by Hero Type and Severity ({fixer})",
            fontsize=13,
            fontweight="bold",
            x=0.02,
            ha="left",
        )
        return self._save_figure(figure, f"figure_3_bug_performance_{fixer}", dpi, save_svg)

    def _plot_figure_4_threshold_sensitivity(self, dpi: int, save_svg: bool) -> Path:
        rows = self._read_csv(self.robustness_csv_path)
        successful_rows = [row for row in rows if row.get("status", "") == "success"]
        if not successful_rows:
            raise ValueError("No successful threshold sweep rows in master CSV.")

        top_values = sorted({float(row["top_fraction"]) for row in successful_rows})
        coverage_values = sorted({float(row["coverage_fraction"]) for row in successful_rows})
        quantile_values = sorted({float(row["hybrid_quantile"]) for row in successful_rows})

        figure, axes = plt.subplots(
            nrows=2,
            ncols=len(quantile_values),
            figsize=(5.2 * len(quantile_values), 8.2),
            constrained_layout=True,
        )

        if len(quantile_values) == 1:
            axes = np.array([[axes[0]], [axes[1]]], dtype=object)

        metric_specs = (
            (
                "technical_overlap_mean_jaccard",
                "Technical overlap mean Jaccard",
                "YlGnBu",
                0.0,
                1.0,
            ),
            (
                "rq3_direction_consistency_share_assignee_fix_rate",
                "RQ3 direction consistency share",
                "YlOrBr",
                0.0,
                1.0,
            ),
        )

        for col_index, quantile in enumerate(quantile_values):
            quantile_rows = [
                row for row in successful_rows if float(row["hybrid_quantile"]) == quantile
            ]
            row_by_cell = {
                (float(row["top_fraction"]), float(row["coverage_fraction"])): row
                for row in quantile_rows
            }

            for row_index, (metric_key, metric_label, cmap, vmin, vmax) in enumerate(metric_specs):
                axis = axes[row_index, col_index]
                grid = np.full((len(coverage_values), len(top_values)), np.nan, dtype=float)
                annotations = [["" for _ in top_values] for _ in coverage_values]

                for coverage_index, coverage_fraction in enumerate(coverage_values):
                    for top_index, top_fraction in enumerate(top_values):
                        row = row_by_cell.get((top_fraction, coverage_fraction))
                        if row is None:
                            continue
                        value = float(row[metric_key])
                        grid[coverage_index, top_index] = value
                        annotations[coverage_index][top_index] = f"{value:.2f}"

                image = axis.imshow(grid, cmap=cmap, vmin=vmin, vmax=vmax)
                axis.set_xticks(np.arange(len(top_values)))
                axis.set_xticklabels([f"{value:.2f}" for value in top_values])
                axis.set_yticks(np.arange(len(coverage_values)))
                axis.set_yticklabels([f"{value:.2f}" for value in coverage_values])
                axis.set_xlabel("top_fraction")
                axis.set_ylabel("coverage_fraction")
                axis.set_title(
                    f"{metric_label}\nq={quantile:.2f}", fontsize=10.5, fontweight="bold"
                )

                for coverage_index in range(len(coverage_values)):
                    for top_index in range(len(top_values)):
                        value = grid[coverage_index, top_index]
                        text = (
                            annotations[coverage_index][top_index] if not np.isnan(value) else "NA"
                        )
                        axis.text(
                            top_index,
                            coverage_index,
                            text,
                            ha="center",
                            va="center",
                            fontsize=8.5,
                            color="white" if not np.isnan(value) and value > 0.55 else "#111111",
                        )

                colorbar = figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
                colorbar.ax.tick_params(labelsize=8)

        figure.suptitle(
            "Figure 4. Threshold Sensitivity Across Top/Coverage/Quantile Settings",
            fontsize=13,
            fontweight="bold",
            x=0.01,
            ha="left",
        )
        return self._save_figure(figure, "figure_4_threshold_sensitivity", dpi, save_svg)
