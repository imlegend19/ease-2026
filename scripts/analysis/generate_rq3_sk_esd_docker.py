"""CLI entrypoint for generating RQ3 SK-ESD rankings via Docker + R."""

import argparse
import subprocess
from pathlib import Path

from core.logging import setup_logging
from core.paths import ensure_directory
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_rankings import DEFAULT_SORT_DIRECTION_BY_METRIC
from pipelines.analysis.rq3_sk_esd import PRIORITY_SEVERITIES
from pipelines.analysis.rq3_sk_esd import Rq3ScottKnottEsdPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate RQ3 SK-ESD rankings using Docker (R runtime) and write "
            "results to artifacts/outputs/csv/analysis/rq3/sk_esd."
        ),
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild reverse-identity cache before running issue metrics.",
    )
    parser.add_argument(
        "--skip-issue-metrics",
        action="store_true",
        help="Skip regenerating fixed/reopened issue metric pickles.",
    )
    parser.add_argument(
        "--skip-input-generation",
        action="store_true",
        help="Skip regenerating SK-ESD input matrices from Python pipeline.",
    )
    parser.add_argument(
        "--docker-image",
        default="rocker/r2u:24.04",
        help="Docker image with R support (default: rocker/r2u:24.04).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _generate_input_matrices_only() -> None:
    issue_metrics = IssueOutcomeMetricsPipeline()
    pipeline = Rq3ScottKnottEsdPipeline()
    ensure_directory(pipeline.output_root)

    for metric_name in DEFAULT_SORT_DIRECTION_BY_METRIC:
        for severity in PRIORITY_SEVERITIES:
            metric_by_hero = issue_metrics.load_metric_pickle(
                metric_name=metric_name, severity=severity
            )
            input_matrix = pipeline._build_input_matrix(metric_by_hero)  # noqa: SLF001
            output_path = pipeline.output_root / f"sk_esd_input_{metric_name}_{severity}.csv"
            input_matrix.to_csv(output_path, index=False)


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    if not args.skip_issue_metrics:
        IssueOutcomeMetricsPipeline().run(
            refresh_identity_cache=args.refresh_identity_cache,
            write_interim=True,
            write_csv=True,
        )

    if not args.skip_input_generation:
        # Build only input matrices here; ranking is performed inside Docker/R.
        _generate_input_matrices_only()

    project_root = Path(__file__).resolve().parents[2]
    sk_esd_rel = Path("artifacts/outputs/csv/analysis/rq3/sk_esd")
    runner_rel = Path("scripts/analysis/rq3_sk_esd_docker_runner.R")

    docker_command = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{project_root.resolve()}:/work",
        "-w",
        "/work",
        args.docker_image,
        "Rscript",
        _as_posix(runner_rel),
        _as_posix(sk_esd_rel),
        _as_posix(sk_esd_rel),
    ]

    subprocess.run(docker_command, check=True)

    print("Generated RQ3 SK-ESD artifacts (Docker):")
    for metric in ("fixed", "reopened"):
        for severity in ("minor", "major", "critical", "trivial", "blocker"):
            path = project_root / sk_esd_rel / f"sk_esd_ranking_{metric}_{severity}.csv"
            print(f"- {metric}/{severity}: {path}")


if __name__ == "__main__":
    main()
