"""RQ3 final-table summaries from computed outcome CSVs."""


import csv
import math
from dataclasses import dataclass
from pathlib import Path

from ease2026.analysis.rq1 import hero_type_from_code
from ease2026.core.logging import get_logger
from ease2026.core.settings import settings

logger = get_logger(__name__)

SEVERITY_ORDER: tuple[str, ...] = ("blocker", "critical", "major", "minor", "trivial")
FIXER_ORDER: tuple[str, ...] = ("assignee", "commit_author")


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
        robustness_path = self._write_operationalization_robustness(records)

        logger.info(
            "Generated RQ3 final tables",
            record_count=len(records),
            summary_table=str(summary_path),
            robustness_table=str(robustness_path),
        )
        return {
            "rq3_type_summary": summary_path,
            "rq3_operationalization_robustness": robustness_path,
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

    def _write_type_summary(self, records: list[OutcomeRecord]) -> Path:
        output_path = self.output_dir / "rq3_type_summary.csv"
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

            for fixer in FIXER_ORDER:
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


def run_rq3_analysis() -> dict[str, Path]:
    return Rq3Analyzer().run()
