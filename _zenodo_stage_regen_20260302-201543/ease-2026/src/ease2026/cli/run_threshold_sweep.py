"""Run threshold robustness sweeps across hero/outcome/analysis pipelines."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ease2026.analysis.rq1 import Rq1Analyzer
from ease2026.analysis.rq2 import Rq2Analyzer
from ease2026.analysis.rq3 import Rq3Analyzer
from ease2026.core.logging import get_logger, setup_logging
from ease2026.core.settings import settings
from ease2026.identity.canonical import load_identity_context
from ease2026.hero.generate import build_hero_flags_and_members, generate_hero_outputs
from ease2026.hero.hybrid import (
    SOCIOTECHNICAL_SPECS,
    SUPER_SPECS,
    TECHNOSOCIAL_SPECS,
    generate_sociotechnical,
    generate_super,
    generate_technosocial,
)
from ease2026.hero.social import (
    compute_comment_count_contributions,
    compute_issue_participation_contributions,
)
from ease2026.hero.technical import (
    compute_commit_count_contributions,
    compute_file_touch_contributions,
    compute_loc_churn_contributions,
)
from ease2026.outcomes.definitions import FixerAttributionPolicy
from ease2026.outcomes.issue_outcomes import IssueOutcomesComputer

logger = get_logger(__name__)

DEFAULT_TOP_FRACTIONS: tuple[float, ...] = (0.15, 0.20, 0.25, 0.30)
DEFAULT_COVERAGE_FRACTIONS: tuple[float, ...] = (0.70, 0.80, 0.85)
DEFAULT_HYBRID_QUANTILES: tuple[float, ...] = (0.50, 0.75)


@dataclass(frozen=True, slots=True)
class SweepConfig:
    top_fraction: float
    coverage_fraction: float
    hybrid_quantile: float


@dataclass(frozen=True, slots=True)
class SweepRunSummary:
    run_id: str
    top_fraction: float
    coverage_fraction: float
    hybrid_quantile: float
    status: str
    run_dir: str
    duration_seconds: float
    technical_overlap_mean_jaccard: float
    social_overlap_jaccard: float
    rq3_direction_preserved_assignee_fix_rate: bool
    rq3_direction_consistency_share_assignee_fix_rate: float
    rq3_direction_rows_assignee_fix_rate: int
    generated_at_utc: str
    error: str


def _parse_fraction_list(raw: str) -> tuple[float, ...]:
    values: list[float] = []
    for token in raw.split(","):
        normalized = token.strip()
        if not normalized:
            continue
        values.append(float(normalized))
    if not values:
        raise ValueError("Expected at least one numeric value.")
    return tuple(values)


def _validate_fraction(value: float, label: str, inclusive_zero: bool = False) -> None:
    lower_ok = value >= 0 if inclusive_zero else value > 0
    if not lower_ok or value > 1:
        if inclusive_zero:
            raise ValueError(f"{label} must be in [0, 1].")
        raise ValueError(f"{label} must be in (0, 1].")


def _format_fraction(value: float) -> str:
    return f"{value:.2f}"


def _run_id(config: SweepConfig) -> str:
    return (
        f"top{_format_fraction(config.top_fraction)}"
        f"_cov{_format_fraction(config.coverage_fraction)}"
        f"_q{_format_fraction(config.hybrid_quantile)}"
    )


def _path_relative_to_experiment_root(path: Path) -> str:
    experiment_root = settings.artifacts_dir.parent.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(experiment_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run robustness sweeps over top-fraction, coverage-fraction, and hybrid-quantile; "
            "write per-run snapshots and a master summary CSV."
        ),
    )
    parser.add_argument(
        "--top-fractions",
        default=",".join(str(value) for value in DEFAULT_TOP_FRACTIONS),
        help="Comma-separated top-fraction values (default: 0.15,0.20,0.25,0.30).",
    )
    parser.add_argument(
        "--coverage-fractions",
        default=",".join(str(value) for value in DEFAULT_COVERAGE_FRACTIONS),
        help="Comma-separated coverage-fraction values (default: 0.70,0.80,0.85).",
    )
    parser.add_argument(
        "--hybrid-quantiles",
        default=",".join(str(value) for value in DEFAULT_HYBRID_QUANTILES),
        help="Comma-separated hybrid-quantile values (default: 0.50,0.75).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit on number of configurations to execute (0 = no limit).",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Overwrite existing run directories for matching configurations.",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Refresh reverse-identity cache from Mongo before running sweep.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    top_fractions = _parse_fraction_list(args.top_fractions)
    coverage_fractions = _parse_fraction_list(args.coverage_fractions)
    hybrid_quantiles = _parse_fraction_list(args.hybrid_quantiles)

    for value in top_fractions:
        _validate_fraction(value, "top fraction")
    for value in coverage_fractions:
        _validate_fraction(value, "coverage fraction")
    for value in hybrid_quantiles:
        _validate_fraction(value, "hybrid quantile", inclusive_zero=True)

    if args.limit < 0:
        parser.error("--limit must be >= 0.")

    args.top_fractions = top_fractions
    args.coverage_fractions = coverage_fractions
    args.hybrid_quantiles = hybrid_quantiles
    return args


def _build_base_contribution_maps(
    *,
    refresh_identity_cache: bool = False,
) -> dict[str, dict[str, dict[object, int]]]:
    reverse_identity_map, reverse_identity_resolver = load_identity_context(
        refresh_cache=refresh_identity_cache
    )
    return {
        "T1": compute_commit_count_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "T2": compute_file_touch_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "T3": compute_loc_churn_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "S1": compute_comment_count_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
        "S2": compute_issue_participation_contributions(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        ),
    }


def _generate_base_heroes(
    contribution_map_by_code: dict[str, dict[str, dict[object, int]]],
    top_fraction: float,
    coverage_fraction: float,
) -> dict[str, dict[str, dict[object, int]]]:
    hero_members_by_code: dict[str, dict[str, dict[object, int]]] = {}
    for code, contribution_map in contribution_map_by_code.items():
        _, hero_members = build_hero_flags_and_members(
            contribution_map=contribution_map,
            top_fraction=top_fraction,
            coverage_fraction=coverage_fraction,
        )
        generate_hero_outputs(
            contribution_map=contribution_map,
            metric_name=code,
            top_fraction=top_fraction,
            coverage_fraction=coverage_fraction,
        )
        hero_members_by_code[code] = hero_members
    return hero_members_by_code


def _generate_hybrid_heroes(
    hero_members_by_code: dict[str, dict[str, dict[object, int]]],
    contribution_map_by_code: dict[str, dict[str, dict[object, int]]],
    hybrid_quantile: float,
) -> None:
    for spec in SOCIOTECHNICAL_SPECS:
        generate_sociotechnical(
            spec=spec,
            hero_members_by_code=hero_members_by_code,
            contribution_map_by_code=contribution_map_by_code,
            quantile=hybrid_quantile,
        )
    for spec in TECHNOSOCIAL_SPECS:
        generate_technosocial(
            spec=spec,
            hero_members_by_code=hero_members_by_code,
            contribution_map_by_code=contribution_map_by_code,
            quantile=hybrid_quantile,
        )
    for spec in SUPER_SPECS:
        generate_super(spec=spec, hero_members_by_code=hero_members_by_code)


def _copy_outputs_to_run_dir(run_dir: Path) -> None:
    run_output_root = run_dir / "outputs" / "csv"
    run_output_root.mkdir(parents=True, exist_ok=True)
    for relative_dir in (Path("heroes"), Path("analysis")):
        source = settings.outputs_csv_dir / relative_dir
        destination = run_output_root / relative_dir
        if not source.exists():
            continue
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "y"}


def _compute_run_indicators() -> tuple[float, float, bool, float, int]:
    final_tables_root = settings.outputs_csv_dir / "analysis" / "final_tables"

    technical_overlap_values: list[float] = []
    technical_path = final_tables_root / "rq2_overlap_technical.csv"
    if technical_path.exists():
        with technical_path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                technical_overlap_values.append(float(row["pair_jaccard"]))
    technical_overlap_mean = (
        float("nan")
        if not technical_overlap_values
        else sum(technical_overlap_values) / len(technical_overlap_values)
    )

    social_overlap = float("nan")
    social_path = final_tables_root / "rq2_overlap_social.csv"
    if social_path.exists():
        with social_path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            first_row = next(reader, None)
            if first_row is not None:
                social_overlap = float(first_row["pair_jaccard"])

    robustness_path = final_tables_root / "rq3_operationalization_robustness.csv"
    direction_values: list[bool] = []
    if robustness_path.exists():
        with robustness_path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("fixer") != "assignee":
                    continue
                if row.get("outcome_metric") != "fix_rate":
                    continue
                direction_values.append(_parse_bool(str(row["direction_consistent_vs_reference"])))

    direction_preserved = all(direction_values) if direction_values else False
    direction_share = (
        float("nan")
        if not direction_values
        else sum(1 for value in direction_values if value) / len(direction_values)
    )
    return (
        technical_overlap_mean,
        social_overlap,
        direction_preserved,
        direction_share,
        len(direction_values),
    )


def _write_master_csv(rows: list[SweepRunSummary]) -> Path:
    output_dir = settings.outputs_csv_dir / "analysis" / "robustness"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "threshold_sweep_master.csv"

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "run_id",
                "top_fraction",
                "coverage_fraction",
                "hybrid_quantile",
                "status",
                "run_dir",
                "duration_seconds",
                "technical_overlap_mean_jaccard",
                "social_overlap_jaccard",
                "rq3_direction_preserved_assignee_fix_rate",
                "rq3_direction_consistency_share_assignee_fix_rate",
                "rq3_direction_rows_assignee_fix_rate",
                "generated_at_utc",
                "error",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.run_id,
                    row.top_fraction,
                    row.coverage_fraction,
                    row.hybrid_quantile,
                    row.status,
                    row.run_dir,
                    row.duration_seconds,
                    row.technical_overlap_mean_jaccard,
                    row.social_overlap_jaccard,
                    row.rq3_direction_preserved_assignee_fix_rate,
                    row.rq3_direction_consistency_share_assignee_fix_rate,
                    row.rq3_direction_rows_assignee_fix_rate,
                    row.generated_at_utc,
                    row.error,
                ]
            )
    return output_path


def _write_run_metadata(run_dir: Path, summary: SweepRunSummary) -> None:
    metadata_path = run_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    configs = [
        SweepConfig(top, cov, q)
        for top, cov, q in itertools.product(
            args.top_fractions,
            args.coverage_fractions,
            args.hybrid_quantiles,
        )
    ]
    if args.limit > 0:
        configs = configs[: args.limit]

    logger.info("Starting threshold sweep", config_count=len(configs))
    contribution_map_by_code = _build_base_contribution_maps(
        refresh_identity_cache=args.refresh_identity_cache
    )
    summaries: list[SweepRunSummary] = []

    runs_root = settings.artifacts_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    for config in configs:
        run_id = _run_id(config)
        run_dir = runs_root / run_id
        run_dir_for_output = _path_relative_to_experiment_root(run_dir)
        start_time = time.perf_counter()
        generated_at = datetime.now(tz=UTC).isoformat()

        if run_dir.exists() and not args.overwrite_existing:
            summary = SweepRunSummary(
                run_id=run_id,
                top_fraction=config.top_fraction,
                coverage_fraction=config.coverage_fraction,
                hybrid_quantile=config.hybrid_quantile,
                status="skipped_exists",
                run_dir=run_dir_for_output,
                duration_seconds=0.0,
                technical_overlap_mean_jaccard=float("nan"),
                social_overlap_jaccard=float("nan"),
                rq3_direction_preserved_assignee_fix_rate=False,
                rq3_direction_consistency_share_assignee_fix_rate=float("nan"),
                rq3_direction_rows_assignee_fix_rate=0,
                generated_at_utc=generated_at,
                error="run directory exists",
            )
            summaries.append(summary)
            logger.warning(
                "Skipping existing run directory (use --overwrite-existing to replace)",
                run_id=run_id,
                run_dir=run_dir_for_output,
            )
            continue

        if run_dir.exists() and args.overwrite_existing:
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(
                "Executing sweep run",
                run_id=run_id,
                top_fraction=config.top_fraction,
                coverage_fraction=config.coverage_fraction,
                hybrid_quantile=config.hybrid_quantile,
            )

            hero_members_by_code = _generate_base_heroes(
                contribution_map_by_code=contribution_map_by_code,
                top_fraction=config.top_fraction,
                coverage_fraction=config.coverage_fraction,
            )
            _generate_hybrid_heroes(
                hero_members_by_code=hero_members_by_code,
                contribution_map_by_code=contribution_map_by_code,
                hybrid_quantile=config.hybrid_quantile,
            )

            IssueOutcomesComputer(
                refresh_identity_cache=args.refresh_identity_cache
            ).compute_and_write(
                fixer_policy=FixerAttributionPolicy.ASSIGNEE,
            )
            Rq1Analyzer().run()
            Rq2Analyzer().run()
            Rq3Analyzer().run()

            (
                technical_overlap_mean,
                social_overlap,
                direction_preserved,
                direction_share,
                direction_rows,
            ) = _compute_run_indicators()

            _copy_outputs_to_run_dir(run_dir)
            duration_seconds = time.perf_counter() - start_time
            summary = SweepRunSummary(
                run_id=run_id,
                top_fraction=config.top_fraction,
                coverage_fraction=config.coverage_fraction,
                hybrid_quantile=config.hybrid_quantile,
                status="success",
                run_dir=run_dir_for_output,
                duration_seconds=duration_seconds,
                technical_overlap_mean_jaccard=technical_overlap_mean,
                social_overlap_jaccard=social_overlap,
                rq3_direction_preserved_assignee_fix_rate=direction_preserved,
                rq3_direction_consistency_share_assignee_fix_rate=direction_share,
                rq3_direction_rows_assignee_fix_rate=direction_rows,
                generated_at_utc=generated_at,
                error="",
            )
            summaries.append(summary)
            _write_run_metadata(run_dir, summary)
            logger.info(
                "Completed sweep run",
                run_id=run_id,
                duration_seconds=duration_seconds,
                technical_overlap_mean_jaccard=technical_overlap_mean,
                rq3_direction_preserved_assignee_fix_rate=direction_preserved,
            )
        except Exception as exc:  # noqa: BLE001
            duration_seconds = time.perf_counter() - start_time
            summary = SweepRunSummary(
                run_id=run_id,
                top_fraction=config.top_fraction,
                coverage_fraction=config.coverage_fraction,
                hybrid_quantile=config.hybrid_quantile,
                status="failed",
                run_dir=run_dir_for_output,
                duration_seconds=duration_seconds,
                technical_overlap_mean_jaccard=float("nan"),
                social_overlap_jaccard=float("nan"),
                rq3_direction_preserved_assignee_fix_rate=False,
                rq3_direction_consistency_share_assignee_fix_rate=float("nan"),
                rq3_direction_rows_assignee_fix_rate=0,
                generated_at_utc=generated_at,
                error=str(exc),
            )
            summaries.append(summary)
            _write_run_metadata(run_dir, summary)
            logger.exception("Sweep run failed", run_id=run_id)

    master_path = _write_master_csv(summaries)
    print(f"Threshold sweep complete. Master summary: {master_path}")
    for summary in summaries:
        print(
            f"- {summary.run_id}: status={summary.status}, "
            f"run_dir={summary.run_dir}, "
            f"technical_overlap_mean_jaccard={summary.technical_overlap_mean_jaccard}, "
            f"rq3_direction_preserved={summary.rq3_direction_preserved_assignee_fix_rate}"
        )


if __name__ == "__main__":
    main()
