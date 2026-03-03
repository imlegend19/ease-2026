"""Reviewer-facing robustness summary for threshold-grid sensitivity checks."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from ease2026.analysis.figures import HERO_TYPE_COLORS, HERO_TYPE_LABELS
from ease2026.analysis.rq1 import HERO_TYPE_ORDER
from ease2026.analysis.rq3 import SEVERITY_ORDER
from ease2026.core.logging import get_logger
from ease2026.core.settings import settings

logger = get_logger(__name__)

TOP_FRACTIONS: tuple[float, ...] = (0.15, 0.20, 0.25, 0.30)
COVERAGE_FRACTIONS: tuple[float, ...] = (0.70, 0.80, 0.85)
HYBRID_QUANTILES: tuple[float, ...] = (0.50, 0.75)
DEFAULT_CONFIG = (0.20, 0.80, 0.50)
MULTIFACETED_TYPES: tuple[str, ...] = ("sociotechnical", "technosocial", "super")
PLOT_HERO_TYPE_ORDER: tuple[str, ...] = HERO_TYPE_ORDER


def _is_nan(value: float) -> bool:
    return math.isnan(value)


def _pair_key(group_a: str, group_b: str) -> tuple[str, str]:
    return tuple(sorted((group_a, group_b)))


def _format_pct(value: float) -> str:
    return f"{value:.2f}%"


def _format_pct_range(minimum: float, maximum: float) -> str:
    return f"{minimum:.2f}%-{maximum:.2f}%"


def _format_fraction(value: float) -> str:
    return f"{value:.2f}"


@dataclass(frozen=True, slots=True)
class NeighborhoodConfig:
    top_fraction: float
    coverage_fraction: float
    hybrid_quantile: float

    @property
    def run_id(self) -> str:
        return (
            f"top{_format_fraction(self.top_fraction)}"
            f"_cov{_format_fraction(self.coverage_fraction)}"
            f"_q{_format_fraction(self.hybrid_quantile)}"
        )

    @property
    def pareto_label(self) -> str:
        return f"{int(round(self.top_fraction * 100))}/{int(round(self.coverage_fraction * 100))}"


@dataclass(frozen=True, slots=True)
class RunObservation:
    config: NeighborhoodConfig
    prevalence_by_type: dict[str, float]
    hero_member_rows_by_type: dict[str, int]
    assignee_reference_codes: dict[tuple[str, str, str], str]
    type_pair_jaccard: dict[tuple[str, str], float]
    assignee_reopen_median: dict[tuple[str, str], float]


@dataclass(frozen=True, slots=True)
class SummaryRow:
    claim_id: str
    finding: str
    default_value: str
    range_across_configs: str
    stable: bool
    support: str


def build_neighborhood_configs() -> tuple[NeighborhoodConfig, ...]:
    configs: list[NeighborhoodConfig] = []
    for top_fraction in TOP_FRACTIONS:
        for coverage_fraction in COVERAGE_FRACTIONS:
            for quantile in HYBRID_QUANTILES:
                configs.append(
                    NeighborhoodConfig(
                        top_fraction=top_fraction,
                        coverage_fraction=coverage_fraction,
                        hybrid_quantile=quantile,
                    )
                )
    return tuple(configs)


def ts_sh_is_strongest_pair(type_pair_jaccard: dict[tuple[str, str], float]) -> bool:
    key = _pair_key("technosocial", "super")
    ts_sh_value = type_pair_jaccard.get(key, float("nan"))
    if _is_nan(ts_sh_value):
        return False
    max_value = max(type_pair_jaccard.values(), default=float("nan"))
    if _is_nan(max_value):
        return False
    return math.isclose(ts_sh_value, max_value, rel_tol=1e-9, abs_tol=1e-12)


def multifaceted_reopen_advantage_share(
    assignee_reopen_median: dict[tuple[str, str], float],
) -> tuple[float, int, int]:
    favorable = 0
    total = 0
    for severity in SEVERITY_ORDER:
        social_value = assignee_reopen_median.get((severity, "social"), float("nan"))
        if _is_nan(social_value):
            continue
        for hero_type in MULTIFACETED_TYPES:
            hero_value = assignee_reopen_median.get((severity, hero_type), float("nan"))
            if _is_nan(hero_value):
                continue
            total += 1
            if hero_value <= social_value:
                favorable += 1

    share = float("nan") if total == 0 else favorable / total
    return share, favorable, total


class ReviewerRobustnessGenerator:
    @property
    def output_csv_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "robustness"

    @property
    def output_plot_dir(self) -> Path:
        return settings.outputs_plots_dir / "analysis" / "reviewer_robustness"

    @property
    def run_root(self) -> Path:
        return settings.artifacts_dir / "runs"

    def run(
        self,
        dpi: int = 300,
        save_svg: bool = True,
    ) -> dict[str, Path]:
        self.output_csv_dir.mkdir(parents=True, exist_ok=True)
        self.output_plot_dir.mkdir(parents=True, exist_ok=True)

        observations = [self._load_observation(config) for config in build_neighborhood_configs()]

        prevalence_long_path = self._write_prevalence_long(observations)
        q_sensitivity_match_path = self._write_q_sensitivity_match_summary(observations)
        summary_path = self._write_summary_table(observations)
        range_figure_path = self._plot_prevalence_range(observations, dpi=dpi, save_svg=save_svg)
        heatmap_figure_path = self._plot_multifaceted_heatmap(
            observations,
            dpi=dpi,
            save_svg=save_svg,
        )

        logger.info(
            "Generated reviewer robustness artifacts",
            config_count=len(observations),
            summary_csv=str(summary_path),
            prevalence_long_csv=str(prevalence_long_path),
            q_sensitivity_match_csv=str(q_sensitivity_match_path),
            range_figure=str(range_figure_path),
            heatmap_figure=str(heatmap_figure_path),
        )
        return {
            "reviewer_robustness_summary_csv": summary_path,
            "reviewer_rq1_prevalence_long_csv": prevalence_long_path,
            "q_sensitivity_match_summary_csv": q_sensitivity_match_path,
            "reviewer_rq1_prevalence_range_figure": range_figure_path,
            "reviewer_rq1_multifaceted_heatmap_figure": heatmap_figure_path,
        }

    def _load_observation(self, config: NeighborhoodConfig) -> RunObservation:
        final_tables_dir = self.run_root / config.run_id / "outputs" / "csv" / "analysis" / "final_tables"
        if not final_tables_dir.exists():
            raise FileNotFoundError(f"Missing run outputs for {config.run_id}: {final_tables_dir}")

        prevalence_by_type = self._load_prevalence_by_type(
            final_tables_dir / "rq1_hero_type_prevalence.csv"
        )
        hero_member_rows_by_type = self._load_hero_member_rows_by_type(
            final_tables_dir / "rq1_hero_type_prevalence.csv"
        )
        type_pair_jaccard = self._load_type_pair_jaccard(
            final_tables_dir / "rq2_overlap_type_groups.csv"
        )
        assignee_reference_codes = self._load_assignee_reference_codes(
            final_tables_dir / "rq3_operationalization_robustness.csv"
        )
        assignee_reopen_median = self._load_assignee_reopen_median(
            final_tables_dir / "rq3_type_summary.csv"
        )
        return RunObservation(
            config=config,
            prevalence_by_type=prevalence_by_type,
            hero_member_rows_by_type=hero_member_rows_by_type,
            assignee_reference_codes=assignee_reference_codes,
            type_pair_jaccard=type_pair_jaccard,
            assignee_reopen_median=assignee_reopen_median,
        )

    def _load_prevalence_by_type(self, csv_path: Path) -> dict[str, float]:
        rows = self._read_csv(csv_path)
        prevalence: dict[str, float] = {}
        for row in rows:
            hero_type = str(row.get("hero_type", "")).strip()
            if hero_type not in PLOT_HERO_TYPE_ORDER:
                continue
            prevalence[hero_type] = float(row["project_prevalence_pct"])
        missing = [hero_type for hero_type in PLOT_HERO_TYPE_ORDER if hero_type not in prevalence]
        if missing:
            raise ValueError(f"Missing prevalence rows for hero types {missing} in {csv_path}")
        return prevalence

    def _load_hero_member_rows_by_type(self, csv_path: Path) -> dict[str, int]:
        rows = self._read_csv(csv_path)
        member_rows: dict[str, int] = {}
        for row in rows:
            hero_type = str(row.get("hero_type", "")).strip()
            if hero_type not in PLOT_HERO_TYPE_ORDER:
                continue
            member_rows[hero_type] = int(row["hero_member_rows_total"])
        missing = [hero_type for hero_type in PLOT_HERO_TYPE_ORDER if hero_type not in member_rows]
        if missing:
            raise ValueError(f"Missing hero-member rows for hero types {missing} in {csv_path}")
        return member_rows

    def _load_assignee_reference_codes(self, csv_path: Path) -> dict[tuple[str, str, str], str]:
        rows = self._read_csv(csv_path)
        values: dict[tuple[str, str, str], str] = {}
        for row in rows:
            if str(row.get("fixer", "")).strip() != "assignee":
                continue
            severity = str(row.get("severity", "")).strip()
            hero_type = str(row.get("hero_type", "")).strip()
            outcome_metric = str(row.get("outcome_metric", "")).strip()
            reference_code = str(row.get("reference_code", "")).strip()
            if not severity or not hero_type or not outcome_metric or not reference_code:
                continue
            values[(severity, hero_type, outcome_metric)] = reference_code
        return values

    def _load_type_pair_jaccard(self, csv_path: Path) -> dict[tuple[str, str], float]:
        rows = self._read_csv(csv_path)
        pair_jaccard: dict[tuple[str, str], float] = {}
        for row in rows:
            group_a = str(row.get("group_a", "")).strip()
            group_b = str(row.get("group_b", "")).strip()
            if not group_a or not group_b:
                continue
            pair_jaccard[_pair_key(group_a, group_b)] = float(row["pair_jaccard"])
        return pair_jaccard

    def _load_assignee_reopen_median(self, csv_path: Path) -> dict[tuple[str, str], float]:
        rows = self._read_csv(csv_path)
        values: dict[tuple[str, str], float] = {}
        for row in rows:
            if str(row.get("fixer", "")).strip() != "assignee":
                continue
            severity = str(row.get("severity", "")).strip()
            hero_type = str(row.get("hero_type", "")).strip()
            if not severity or not hero_type:
                continue
            values[(severity, hero_type)] = float(row["reopen_rate_median"])
        return values

    def _write_prevalence_long(self, observations: list[RunObservation]) -> Path:
        output_path = self.output_csv_dir / "reviewer_rq1_prevalence_long.csv"
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "run_id",
                    "pareto_label",
                    "top_fraction",
                    "coverage_fraction",
                    "hybrid_quantile",
                    "hero_type",
                    "project_prevalence_pct",
                ]
            )
            for observation in observations:
                for hero_type in PLOT_HERO_TYPE_ORDER:
                    writer.writerow(
                        [
                            observation.config.run_id,
                            observation.config.pareto_label,
                            observation.config.top_fraction,
                            observation.config.coverage_fraction,
                            observation.config.hybrid_quantile,
                            hero_type,
                            observation.prevalence_by_type[hero_type],
                        ]
                    )
        return output_path

    def _write_q_sensitivity_match_summary(self, observations: list[RunObservation]) -> Path:
        by_key = {
            (
                observation.config.top_fraction,
                observation.config.coverage_fraction,
                observation.config.hybrid_quantile,
            ): observation
            for observation in observations
        }
        output_path = self.output_csv_dir / "q_sensitivity_match_summary.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rows: list[list[object]] = []
        for top_fraction in TOP_FRACTIONS:
            for coverage_fraction in COVERAGE_FRACTIONS:
                q50_key = (top_fraction, coverage_fraction, 0.50)
                q75_key = (top_fraction, coverage_fraction, 0.75)
                if q50_key not in by_key or q75_key not in by_key:
                    raise ValueError(
                        "Missing q-paired observations for "
                        f"top={top_fraction}, coverage={coverage_fraction}."
                    )
                q50 = by_key[q50_key]
                q75 = by_key[q75_key]

                prevalence_total = len(PLOT_HERO_TYPE_ORDER)
                prevalence_match_count = sum(
                    1
                    for hero_type in PLOT_HERO_TYPE_ORDER
                    if math.isclose(
                        q50.prevalence_by_type[hero_type],
                        q75.prevalence_by_type[hero_type],
                        rel_tol=1e-9,
                        abs_tol=1e-12,
                    )
                )

                shared_code_keys = sorted(
                    set(q50.assignee_reference_codes).intersection(q75.assignee_reference_codes)
                )
                top_code_total = len(shared_code_keys)
                top_code_match_count = sum(
                    1
                    for key in shared_code_keys
                    if q50.assignee_reference_codes[key] == q75.assignee_reference_codes[key]
                )

                st_baseline = q50.hero_member_rows_by_type["sociotechnical"]
                ts_baseline = q50.hero_member_rows_by_type["technosocial"]
                st_reduction = float("nan")
                ts_reduction = float("nan")
                if st_baseline > 0:
                    st_reduction = (
                        (st_baseline - q75.hero_member_rows_by_type["sociotechnical"])
                        / st_baseline
                        * 100.0
                    )
                if ts_baseline > 0:
                    ts_reduction = (
                        (ts_baseline - q75.hero_member_rows_by_type["technosocial"])
                        / ts_baseline
                        * 100.0
                    )

                rows.append(
                    [
                        f"{top_fraction:.2f}",
                        f"{coverage_fraction:.2f}",
                        prevalence_match_count,
                        prevalence_total,
                        top_code_match_count,
                        top_code_total,
                        st_reduction,
                        ts_reduction,
                    ]
                )

        prevalence_match_total = sum(int(row[2]) for row in rows)
        prevalence_total_total = sum(int(row[3]) for row in rows)
        top_code_match_total = sum(int(row[4]) for row in rows)
        top_code_total_total = sum(int(row[5]) for row in rows)
        st_reductions = [float(row[6]) for row in rows if not _is_nan(float(row[6]))]
        ts_reductions = [float(row[7]) for row in rows if not _is_nan(float(row[7]))]
        st_reduction_mean = (
            float("nan")
            if not st_reductions
            else float(np.mean(np.array(st_reductions, dtype=float)))
        )
        ts_reduction_mean = (
            float("nan")
            if not ts_reductions
            else float(np.mean(np.array(ts_reductions, dtype=float)))
        )

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "top_fraction",
                    "coverage_fraction",
                    "prevalence_match_count",
                    "prevalence_total_count",
                    "top_code_match_count",
                    "top_code_total_count",
                    "st_member_row_reduction_pct",
                    "ts_member_row_reduction_pct",
                ]
            )
            for row in rows:
                writer.writerow(row)
            writer.writerow(
                [
                    "ALL",
                    "ALL",
                    prevalence_match_total,
                    prevalence_total_total,
                    top_code_match_total,
                    top_code_total_total,
                    st_reduction_mean,
                    ts_reduction_mean,
                ]
            )

        return output_path

    def _write_summary_table(self, observations: list[RunObservation]) -> Path:
        default_observation = self._observation_for_config(observations, DEFAULT_CONFIG)
        prevalence_values = {
            hero_type: [obs.prevalence_by_type[hero_type] for obs in observations]
            for hero_type in PLOT_HERO_TYPE_ORDER
        }

        ts_sh_jaccard_values = [
            obs.type_pair_jaccard[_pair_key("technosocial", "super")] for obs in observations
        ]
        ts_sh_strongest_count = sum(
            1 for obs in observations if ts_sh_is_strongest_pair(obs.type_pair_jaccard)
        )

        reopen_advantages = [multifaceted_reopen_advantage_share(obs.assignee_reopen_median) for obs in observations]
        reopen_share_values = [share for share, _favorable, _total in reopen_advantages]
        reopen_all_count = sum(1 for share, favorable, total in reopen_advantages if total > 0 and favorable == total)
        default_reopen_share, default_favorable, default_total = multifaceted_reopen_advantage_share(
            default_observation.assignee_reopen_median
        )

        st_less_social_count = sum(
            1
            for obs in observations
            if obs.prevalence_by_type["sociotechnical"] < obs.prevalence_by_type["social"]
        )
        ts_less_technical_count = sum(
            1
            for obs in observations
            if obs.prevalence_by_type["technosocial"] < obs.prevalence_by_type["technical"]
        )
        sh_not_above_ts_count = sum(
            1
            for obs in observations
            if obs.prevalence_by_type["super"] <= obs.prevalence_by_type["technosocial"]
        )
        high_prevalence_count = sum(
            1
            for obs in observations
            if obs.prevalence_by_type["technical"] > 50.0 and obs.prevalence_by_type["social"] > 50.0
        )

        rows = [
            SummaryRow(
                claim_id="RQ1-A",
                finding="Technical and social hero-project prevalence remains high.",
                default_value=(
                    f"T={_format_pct(default_observation.prevalence_by_type['technical'])}; "
                    f"S={_format_pct(default_observation.prevalence_by_type['social'])}"
                ),
                range_across_configs=(
                    f"T {_format_pct_range(min(prevalence_values['technical']), max(prevalence_values['technical']))}; "
                    f"S {_format_pct_range(min(prevalence_values['social']), max(prevalence_values['social']))}"
                ),
                stable=high_prevalence_count == len(observations),
                support=f"{high_prevalence_count}/{len(observations)}",
            ),
            SummaryRow(
                claim_id="RQ1-B",
                finding="Sociotechnical prevalence stays lower than social prevalence.",
                default_value=(
                    f"ST={_format_pct(default_observation.prevalence_by_type['sociotechnical'])}; "
                    f"S={_format_pct(default_observation.prevalence_by_type['social'])}"
                ),
                range_across_configs=(
                    f"ST {_format_pct_range(min(prevalence_values['sociotechnical']), max(prevalence_values['sociotechnical']))}; "
                    f"S {_format_pct_range(min(prevalence_values['social']), max(prevalence_values['social']))}"
                ),
                stable=st_less_social_count == len(observations),
                support=f"{st_less_social_count}/{len(observations)}",
            ),
            SummaryRow(
                claim_id="RQ1-C",
                finding="Technosocial prevalence stays lower than technical prevalence.",
                default_value=(
                    f"TS={_format_pct(default_observation.prevalence_by_type['technosocial'])}; "
                    f"T={_format_pct(default_observation.prevalence_by_type['technical'])}"
                ),
                range_across_configs=(
                    f"TS {_format_pct_range(min(prevalence_values['technosocial']), max(prevalence_values['technosocial']))}; "
                    f"T {_format_pct_range(min(prevalence_values['technical']), max(prevalence_values['technical']))}"
                ),
                stable=ts_less_technical_count == len(observations),
                support=f"{ts_less_technical_count}/{len(observations)}",
            ),
            SummaryRow(
                claim_id="RQ1-D",
                finding=(
                    "Superhero prevalence stays low and does not exceed technosocial prevalence "
                    "(rarest/tied-rarest multifaceted pattern)."
                ),
                default_value=(
                    f"SH={_format_pct(default_observation.prevalence_by_type['super'])}; "
                    f"TS={_format_pct(default_observation.prevalence_by_type['technosocial'])}"
                ),
                range_across_configs=(
                    f"SH {_format_pct_range(min(prevalence_values['super']), max(prevalence_values['super']))}; "
                    f"TS {_format_pct_range(min(prevalence_values['technosocial']), max(prevalence_values['technosocial']))}"
                ),
                stable=sh_not_above_ts_count == len(observations),
                support=f"{sh_not_above_ts_count}/{len(observations)}",
            ),
            SummaryRow(
                claim_id="RQ2-A",
                finding="Technosocial--Super remains the strongest type-level overlap pair.",
                default_value=f"Jaccard={default_observation.type_pair_jaccard[_pair_key('technosocial', 'super')]:.3f}",
                range_across_configs=f"{min(ts_sh_jaccard_values):.3f}-{max(ts_sh_jaccard_values):.3f}",
                stable=ts_sh_strongest_count == len(observations),
                support=f"{ts_sh_strongest_count}/{len(observations)}",
            ),
            SummaryRow(
                claim_id="RQ3-A",
                finding=(
                    "Multifaceted types keep lower-or-equal median reopen rates than social "
                    "(assignee, severity-wise comparisons)."
                ),
                default_value=(
                    f"{default_favorable}/{default_total} comparisons "
                    f"({_format_pct(default_reopen_share * 100 if not _is_nan(default_reopen_share) else float('nan'))})"
                ),
                range_across_configs=(
                    f"{_format_pct_range(min(value * 100 for value in reopen_share_values), max(value * 100 for value in reopen_share_values))}"
                ),
                stable=reopen_all_count == len(observations),
                support=f"{reopen_all_count}/{len(observations)}",
            ),
        ]

        output_path = self.output_csv_dir / "reviewer_robustness_summary.csv"
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "claim_id",
                    "finding",
                    "default_value",
                    "range_across_configs",
                    "stable",
                    "support",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.claim_id,
                        row.finding,
                        row.default_value,
                        row.range_across_configs,
                        row.stable,
                        row.support,
                    ]
                )
        return output_path

    def _observation_for_config(
        self,
        observations: list[RunObservation],
        config: tuple[float, float, float],
    ) -> RunObservation:
        for observation in observations:
            if (
                math.isclose(observation.config.top_fraction, config[0])
                and math.isclose(observation.config.coverage_fraction, config[1])
                and math.isclose(observation.config.hybrid_quantile, config[2])
            ):
                return observation
        raise ValueError(f"Missing default configuration observation: {config}")

    def _plot_prevalence_range(
        self,
        observations: list[RunObservation],
        dpi: int,
        save_svg: bool,
    ) -> Path:
        default_observation = self._observation_for_config(observations, DEFAULT_CONFIG)
        values_by_type = {
            hero_type: [obs.prevalence_by_type[hero_type] for obs in observations]
            for hero_type in PLOT_HERO_TYPE_ORDER
        }

        x_positions = np.arange(len(PLOT_HERO_TYPE_ORDER))
        minima = np.array([min(values_by_type[hero_type]) for hero_type in PLOT_HERO_TYPE_ORDER], dtype=float)
        maxima = np.array([max(values_by_type[hero_type]) for hero_type in PLOT_HERO_TYPE_ORDER], dtype=float)
        medians = np.array(
            [float(np.median(values_by_type[hero_type])) for hero_type in PLOT_HERO_TYPE_ORDER],
            dtype=float,
        )
        defaults = np.array(
            [default_observation.prevalence_by_type[hero_type] for hero_type in PLOT_HERO_TYPE_ORDER],
            dtype=float,
        )

        figure, axis = plt.subplots(figsize=(10.5, 5.8))

        for index, hero_type in enumerate(PLOT_HERO_TYPE_ORDER):
            color = HERO_TYPE_COLORS.get(hero_type, "#4A5568")
            axis.vlines(x_positions[index], minima[index], maxima[index], color=color, linewidth=4.0, alpha=0.7)
            axis.hlines(
                minima[index],
                x_positions[index] - 0.16,
                x_positions[index] + 0.16,
                color=color,
                linewidth=2.0,
            )
            axis.hlines(
                maxima[index],
                x_positions[index] - 0.16,
                x_positions[index] + 0.16,
                color=color,
                linewidth=2.0,
            )
            axis.scatter(
                x_positions[index],
                medians[index],
                marker="s",
                s=46,
                color=color,
                edgecolor="#1A202C",
                linewidth=0.5,
                zorder=4,
            )
            axis.scatter(
                x_positions[index],
                defaults[index],
                marker="o",
                s=54,
                color="#111111",
                edgecolor="white",
                linewidth=0.6,
                zorder=5,
            )

        axis.set_xticks(x_positions)
        axis.set_xticklabels([HERO_TYPE_LABELS[hero_type] for hero_type in PLOT_HERO_TYPE_ORDER])
        axis.set_ylabel("Project prevalence (%)")
        axis.set_ylim(0, 100)
        axis.grid(axis="y", alpha=0.22)
        axis.set_axisbelow(True)
        axis.set_title(
            "Robustness Figure A. Hero-Type Prevalence Across Threshold Grid",
            loc="left",
            fontsize=12.5,
            fontweight="bold",
        )

        legend_handles = [
            Line2D([0], [0], color="#4A5568", linewidth=4.0, label="Min-max across 24 configs"),
            Line2D(
                [0],
                [0],
                marker="s",
                markersize=7,
                linewidth=0,
                markerfacecolor="#4A5568",
                markeredgecolor="#1A202C",
                label="Neighborhood median",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                markersize=7,
                linewidth=0,
                markerfacecolor="#111111",
                markeredgecolor="white",
                label="Default (20/80, q=0.50)",
            ),
        ]
        axis.legend(handles=legend_handles, loc="upper right", fontsize=8.8, frameon=True)
        axis.text(
            0.01,
            -0.21,
            "Grid: alpha {0.15,0.20,0.25,0.30} x beta {0.70,0.80,0.85} x q {0.50,0.75}.",
            transform=axis.transAxes,
            fontsize=8.8,
            color="#2D3748",
        )

        return self._save_figure(
            figure=figure,
            stem="reviewer_rq1_prevalence_range",
            dpi=dpi,
            save_svg=save_svg,
        )

    def _plot_multifaceted_heatmap(
        self,
        observations: list[RunObservation],
        dpi: int,
        save_svg: bool,
    ) -> Path:
        index_lookup = {
            (obs.config.top_fraction, obs.config.coverage_fraction, obs.config.hybrid_quantile): obs
            for obs in observations
        }
        alpha_beta_pairs = [
            (top_fraction, coverage_fraction)
            for top_fraction in TOP_FRACTIONS
            for coverage_fraction in COVERAGE_FRACTIONS
        ]
        row_labels = [f"a={top:.2f}, b={cov:.2f}" for top, cov in alpha_beta_pairs]
        col_labels = [f"q={quantile:.2f}" for quantile in HYBRID_QUANTILES]

        grid_by_type: dict[str, np.ndarray] = {}
        all_values: list[float] = []
        for hero_type in MULTIFACETED_TYPES:
            grid = np.full((len(alpha_beta_pairs), len(HYBRID_QUANTILES)), np.nan, dtype=float)
            for row_index, (top_fraction, coverage_fraction) in enumerate(alpha_beta_pairs):
                for col_index, quantile in enumerate(HYBRID_QUANTILES):
                    observation = index_lookup.get((top_fraction, coverage_fraction, quantile))
                    if observation is None:
                        continue
                    value = observation.prevalence_by_type[hero_type]
                    grid[row_index, col_index] = value
                    all_values.append(value)
            grid_by_type[hero_type] = grid

        vmin = min(all_values) if all_values else 0.0
        vmax = max(all_values) if all_values else 1.0
        if math.isclose(vmin, vmax):
            vmax = vmin + 1.0

        figure, axes = plt.subplots(
            nrows=1,
            ncols=len(MULTIFACETED_TYPES),
            figsize=(13.8, 8.4),
            constrained_layout=True,
        )
        axes_array = np.atleast_1d(axes)

        for axis, hero_type in zip(axes_array, MULTIFACETED_TYPES, strict=True):
            grid = grid_by_type[hero_type]
            image = axis.imshow(grid, cmap="YlGnBu", vmin=vmin, vmax=vmax)
            axis.set_xticks(np.arange(len(col_labels)))
            axis.set_xticklabels(col_labels)
            axis.set_yticks(np.arange(len(row_labels)))
            axis.set_yticklabels(row_labels)
            axis.set_xlabel("Hybrid threshold")
            axis.set_ylabel("Alpha/Beta pair")
            axis.set_title(HERO_TYPE_LABELS[hero_type], fontsize=11.5, fontweight="bold")

            for row_index in range(grid.shape[0]):
                for col_index in range(grid.shape[1]):
                    value = grid[row_index, col_index]
                    text = "NA" if np.isnan(value) else f"{value:.1f}"
                    color = "white" if (not np.isnan(value) and value > (vmin + vmax) / 2.0) else "#111111"
                    axis.text(
                        col_index,
                        row_index,
                        text,
                        ha="center",
                        va="center",
                        fontsize=9.0,
                        color=color,
                    )

            colorbar = figure.colorbar(image, ax=axis, fraction=0.048, pad=0.04)
            colorbar.set_label("Prevalence (%)", fontsize=8.8)
            colorbar.ax.tick_params(labelsize=8)

        figure.suptitle(
            "Robustness Figure B. Multifaceted Prevalence Heatmap Across Threshold Grid",
            fontsize=12.8,
            fontweight="bold",
            x=0.02,
            ha="left",
        )
        return self._save_figure(
            figure=figure,
            stem="reviewer_rq1_multifaceted_heatmap",
            dpi=dpi,
            save_svg=save_svg,
        )

    def _read_csv(self, csv_path: Path) -> list[dict[str, str]]:
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing required CSV: {csv_path}")
        with csv_path.open("r", newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def _save_figure(self, figure: plt.Figure, stem: str, dpi: int, save_svg: bool) -> Path:
        png_path = self.output_plot_dir / f"{stem}.png"
        figure.savefig(png_path, dpi=dpi, bbox_inches="tight")
        if save_svg:
            svg_path = self.output_plot_dir / f"{stem}.svg"
            figure.savefig(svg_path, bbox_inches="tight")
        plt.close(figure)
        return png_path
