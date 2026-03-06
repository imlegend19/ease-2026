"""RQ3 final-table summaries from computed outcome CSVs."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from scipy.stats import mannwhitneyu

from ease2026.analysis.rq1 import hero_type_from_code
from ease2026.core.logging import get_logger
from ease2026.core.settings import settings
from ease2026.outcomes.definitions import FixerAttributionPolicy

logger = get_logger(__name__)

SEVERITY_ORDER: tuple[str, ...] = ("blocker", "critical", "major", "minor", "trivial")
FIXER_ORDER: tuple[str, ...] = (
    FixerAttributionPolicy.ASSIGNEE.value,
    FixerAttributionPolicy.ASSIGNEE_AT_FIX_TIME.value,
    FixerAttributionPolicy.COMMIT_AUTHOR.value,
    FixerAttributionPolicy.COMBINED.value,
)
AGGREGATED_HERO_TYPE_ORDER: tuple[str, ...] = (
    "technical",
    "social",
    "sociotechnical",
    "technosocial",
    "super",
)


@dataclass(frozen=True, slots=True)
class OutcomeRecord:
    fixer: str
    severity: str
    project_name: str
    hero_code: str
    hero_type: str
    n_assigned: int
    n_fixed: int
    n_reopened: int
    fix_rate: float
    reopen_rate: float


def _parse_float(value: str) -> float:
    normalized = value.strip().lower()
    if normalized in {"nan", ""}:
        return float("nan")
    return float(normalized)


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _median(values: list[float]) -> float:
    return _quantile(values, 0.5)


def _iqr(values: list[float]) -> float:
    if not values:
        return float("nan")
    q1 = _quantile(values, 0.25)
    q3 = _quantile(values, 0.75)
    return q3 - q1


def _is_nan(value: float) -> bool:
    return math.isnan(value)


def _cliffs_delta(sample_a: list[float], sample_b: list[float]) -> float:
    """Return Cliff's delta for two independent samples.

    Positive values indicate sample_a tends to have larger values than sample_b.
    """
    if not sample_a or not sample_b:
        return float("nan")

    n_pairs = len(sample_a) * len(sample_b)
    greater = 0
    lower = 0
    for value_a in sample_a:
        for value_b in sample_b:
            if value_a > value_b:
                greater += 1
            elif value_a < value_b:
                lower += 1
    return (greater - lower) / n_pairs


def _mannwhitney_two_sided_pvalue(sample_a: list[float], sample_b: list[float]) -> float:
    if not sample_a or not sample_b:
        return float("nan")
    try:
        result = mannwhitneyu(sample_a, sample_b, alternative="two-sided", method="auto")
    except ValueError:
        return float("nan")
    return float(result.pvalue)


class Rq3Analyzer:
    @property
    def outcomes_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3_outcomes"

    @property
    def output_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "final_tables"

    def run(self) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        records = self._load_records()
        summary_path = self._write_type_summary(records)
        aggregated_leaders_path = self._write_aggregated_leaders_assignee(records)
        combined_summary_path = self._write_type_summary(
            records,
            output_filename="rq3_type_summary_combined.csv",
            include_fixers={FixerAttributionPolicy.COMBINED.value},
        )
        robustness_path = self._write_operationalization_robustness(records)
        reopen_significance_path = self._write_reopen_rate_social_multifaceted_significance(records)

        logger.info(
            "Generated RQ3 final tables",
            record_count=len(records),
            summary_table=str(summary_path),
            aggregated_leaders_table=str(aggregated_leaders_path),
            combined_summary_table=str(combined_summary_path),
            robustness_table=str(robustness_path),
            reopen_significance_table=str(reopen_significance_path),
        )
        return {
            "rq3_type_summary": summary_path,
            "rq3_aggregated_leaders_assignee": aggregated_leaders_path,
            "rq3_type_summary_combined": combined_summary_path,
            "rq3_operationalization_robustness": robustness_path,
            "rq3_reopen_social_multifaceted_significance": reopen_significance_path,
        }

    def _load_records(self) -> list[OutcomeRecord]:
        records: list[OutcomeRecord] = []
        for fixer in FIXER_ORDER:
            fixer_root = self.outcomes_root / fixer
            if not fixer_root.exists():
                logger.warning(
                    "RQ3 outcomes directory missing; skipping fixer",
                    fixer=fixer,
                    path=str(fixer_root),
                )
                continue

            for severity in SEVERITY_ORDER:
                csv_path = fixer_root / f"{severity}.csv"
                if not csv_path.exists():
                    logger.warning(
                        "RQ3 outcome CSV missing; skipping severity",
                        fixer=fixer,
                        severity=severity,
                        path=str(csv_path),
                    )
                    continue

                with csv_path.open("r", newline="", encoding="utf-8") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        hero_code = str(row.get("hero_code", "")).strip()
                        project_name = str(row.get("project_name", "")).strip().lower()
                        if not hero_code or not project_name:
                            continue

                        records.append(
                            OutcomeRecord(
                                fixer=fixer,
                                severity=severity,
                                project_name=project_name,
                                hero_code=hero_code,
                                hero_type=hero_type_from_code(hero_code),
                                n_assigned=int(row.get("n_assigned", "0")),
                                n_fixed=int(row.get("n_fixed", "0")),
                                n_reopened=int(row.get("n_reopened", "0")),
                                fix_rate=_parse_float(str(row.get("fix_rate", "nan"))),
                                reopen_rate=_parse_float(str(row.get("reopen_rate", "nan"))),
                            )
                        )
        return records

    def _write_type_summary(
        self,
        records: list[OutcomeRecord],
        output_filename: str = "rq3_type_summary.csv",
        include_fixers: set[str] | None = None,
    ) -> Path:
        output_path = self.output_dir / output_filename
        selected_fixers = (
            tuple(fixer for fixer in FIXER_ORDER if fixer in include_fixers)
            if include_fixers is not None
            else FIXER_ORDER
        )
        grouped: dict[tuple[str, str, str], list[OutcomeRecord]] = {}
        for record in records:
            if record.fixer not in selected_fixers:
                continue
            grouped.setdefault((record.fixer, record.severity, record.hero_type), []).append(record)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "fixer",
                    "severity",
                    "hero_type",
                    "n_rows_total",
                    "n_rows_with_assigned",
                    "n_projects_total",
                    "n_projects_with_assigned",
                    "total_n_assigned",
                    "total_n_fixed",
                    "total_n_reopened",
                    "fix_rate_median",
                    "fix_rate_iqr",
                    "reopen_rate_median",
                    "reopen_rate_iqr",
                ]
            )

            for fixer in selected_fixers:
                for severity in SEVERITY_ORDER:
                    hero_types = sorted(
                        {key[2] for key in grouped if key[0] == fixer and key[1] == severity}
                    )
                    for hero_type in hero_types:
                        rows = grouped[(fixer, severity, hero_type)]
                        rows_with_assigned = [row for row in rows if row.n_assigned > 0]
                        projects_total = {row.project_name for row in rows}
                        projects_with_assigned = {row.project_name for row in rows_with_assigned}

                        fix_rates = [
                            row.fix_rate for row in rows_with_assigned if not _is_nan(row.fix_rate)
                        ]
                        reopen_rates = [
                            row.reopen_rate
                            for row in rows_with_assigned
                            if not _is_nan(row.reopen_rate)
                        ]

                        writer.writerow(
                            [
                                fixer,
                                severity,
                                hero_type,
                                len(rows),
                                len(rows_with_assigned),
                                len(projects_total),
                                len(projects_with_assigned),
                                sum(row.n_assigned for row in rows),
                                sum(row.n_fixed for row in rows),
                                sum(row.n_reopened for row in rows),
                                _median(fix_rates),
                                _iqr(fix_rates),
                                _median(reopen_rates),
                                _iqr(reopen_rates),
                            ]
                        )
        return output_path

    def _write_aggregated_leaders_assignee(self, records: list[OutcomeRecord]) -> Path:
        output_path = self.output_dir / "rq3_aggregated_leaders_assignee.csv"
        assignee_records = [
            record
            for record in records
            if record.fixer == FixerAttributionPolicy.ASSIGNEE.value
            and record.hero_type in AGGREGATED_HERO_TYPE_ORDER
        ]

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "severity",
                    "outcome_metric",
                    "winner_hero_type",
                    "winner_median",
                    "winner_n_projects_with_data",
                    "tied_hero_types",
                ]
            )

            for severity in SEVERITY_ORDER:
                severity_records = [
                    record for record in assignee_records if record.severity == severity
                ]
                for outcome_metric in ("reopen_rate", "fix_rate"):
                    values_by_type: dict[str, list[float]] = {}
                    projects_by_type: dict[str, set[str]] = {}
                    for hero_type in AGGREGATED_HERO_TYPE_ORDER:
                        values_by_type[hero_type] = []
                        projects_by_type[hero_type] = set()

                    for record in severity_records:
                        value = (
                            record.reopen_rate
                            if outcome_metric == "reopen_rate"
                            else record.fix_rate
                        )
                        if record.n_assigned == 0 or _is_nan(value):
                            continue
                        values_by_type[record.hero_type].append(value)
                        projects_by_type[record.hero_type].add(record.project_name)

                    medians_by_type = {
                        hero_type: _median(values)
                        for hero_type, values in values_by_type.items()
                        if values
                    }
                    if not medians_by_type:
                        continue

                    if outcome_metric == "reopen_rate":
                        best_value = min(medians_by_type.values())
                    else:
                        best_value = max(medians_by_type.values())

                    tied_types = [
                        hero_type
                        for hero_type in AGGREGATED_HERO_TYPE_ORDER
                        if hero_type in medians_by_type
                        and math.isclose(
                            medians_by_type[hero_type], best_value, rel_tol=1e-12, abs_tol=1e-12
                        )
                    ]
                    winner_hero_type = tied_types[0]
                    writer.writerow(
                        [
                            severity,
                            outcome_metric,
                            winner_hero_type,
                            medians_by_type[winner_hero_type],
                            len(projects_by_type[winner_hero_type]),
                            ",".join(tied_types),
                        ]
                    )

        return output_path

    def _write_operationalization_robustness(
        self,
        records: list[OutcomeRecord],
    ) -> Path:
        output_path = self.output_dir / "rq3_operationalization_robustness.csv"

        grouped: dict[tuple[str, str, str], list[OutcomeRecord]] = {}
        for record in records:
            grouped.setdefault((record.fixer, record.severity, record.hero_type), []).append(record)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "fixer",
                    "severity",
                    "hero_type",
                    "outcome_metric",
                    "reference_code",
                    "n_codes_with_data",
                    "direction_consistent_vs_reference",
                    "code_medians",
                ]
            )

            for (fixer, severity, hero_type), rows in sorted(grouped.items()):
                code_to_rows: dict[str, list[OutcomeRecord]] = {}
                for row in rows:
                    code_to_rows.setdefault(row.hero_code, []).append(row)
                if len(code_to_rows) <= 1:
                    continue

                for outcome_metric in ("fix_rate", "reopen_rate"):
                    code_medians: dict[str, float] = {}
                    for hero_code, code_rows in code_to_rows.items():
                        values: list[float] = []
                        for row in code_rows:
                            if row.n_assigned == 0:
                                continue
                            value = (
                                row.fix_rate if outcome_metric == "fix_rate" else row.reopen_rate
                            )
                            if _is_nan(value):
                                continue
                            values.append(value)
                        if values:
                            code_medians[hero_code] = _median(values)

                    if len(code_medians) <= 1:
                        continue

                    ordered_codes = sorted(code_medians)
                    reference_code = ordered_codes[0]
                    reference_median = code_medians[reference_code]

                    directions: set[int] = set()
                    for hero_code in ordered_codes[1:]:
                        delta = code_medians[hero_code] - reference_median
                        if delta > 0:
                            directions.add(1)
                        elif delta < 0:
                            directions.add(-1)

                    direction_consistent = len(directions) <= 1
                    code_medians_serialized = "; ".join(
                        f"{hero_code}:{code_medians[hero_code]:.6f}" for hero_code in ordered_codes
                    )

                    writer.writerow(
                        [
                            fixer,
                            severity,
                            hero_type,
                            outcome_metric,
                            reference_code,
                            len(code_medians),
                            direction_consistent,
                            code_medians_serialized,
                        ]
                    )

        return output_path

    def _project_reopen_rates(
        self,
        records: list[OutcomeRecord],
        fixer: str,
        severity: str,
        hero_type: str,
    ) -> list[float]:
        values_by_project: dict[str, list[float]] = {}
        for record in records:
            if (
                record.fixer != fixer
                or record.severity != severity
                or record.hero_type != hero_type
            ):
                continue
            if record.n_assigned <= 0 or _is_nan(record.reopen_rate):
                continue
            values_by_project.setdefault(record.project_name, []).append(record.reopen_rate)

        return [_median(values) for _project_name, values in sorted(values_by_project.items())]

    def _write_reopen_rate_social_multifaceted_significance(
        self,
        records: list[OutcomeRecord],
    ) -> Path:
        output_path = self.output_dir / "rq3_reopen_social_multifaceted_significance.csv"
        fixer = FixerAttributionPolicy.ASSIGNEE.value
        comparisons: tuple[tuple[str, str], ...] = (
            ("social_vs_sociotechnical", "sociotechnical"),
            ("social_vs_super", "super"),
        )

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "fixer",
                    "severity",
                    "comparison",
                    "n_projects_social",
                    "n_projects_comparison",
                    "cliffs_delta_social_minus_comparison",
                    "mannwhitney_p_value",
                ]
            )
            for severity in SEVERITY_ORDER:
                social_values = self._project_reopen_rates(
                    records=records,
                    fixer=fixer,
                    severity=severity,
                    hero_type="social",
                )
                for comparison_name, comparison_hero_type in comparisons:
                    comparison_values = self._project_reopen_rates(
                        records=records,
                        fixer=fixer,
                        severity=severity,
                        hero_type=comparison_hero_type,
                    )
                    writer.writerow(
                        [
                            fixer,
                            severity,
                            comparison_name,
                            len(social_values),
                            len(comparison_values),
                            _cliffs_delta(social_values, comparison_values),
                            _mannwhitney_two_sided_pvalue(social_values, comparison_values),
                        ]
                    )
        return output_path


def run_rq3_analysis() -> dict[str, Path]:
    return Rq3Analyzer().run()
