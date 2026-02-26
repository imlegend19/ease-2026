"""CLI entrypoint for SANER-style Kendall Tau outputs for RQ3."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_legacy_exports import Rq3LegacyExportPipeline
from pipelines.analysis.rq3_rankings import Rq3RankingPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Kendall Tau outputs in SANER-compatible file names "
            "(fixed_kendall_tau.csv, reopened_kendall_tau.csv)."
        ),
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild reverse-identity cache before running issue metrics.",
    )
    parser.add_argument(
        "--skip-rankings",
        action="store_true",
        help="Skip regenerating mean ranking and Kendall Tau sources.",
    )
    parser.add_argument(
        "--skip-issue-metrics",
        action="store_true",
        help="Skip regenerating fixed/reopened issue metric artifacts.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    if not args.skip_rankings:
        if not args.skip_issue_metrics:
            IssueOutcomeMetricsPipeline().run(
                refresh_identity_cache=args.refresh_identity_cache,
                write_interim=True,
                write_csv=True,
            )
        Rq3RankingPipeline().run_all()

    output_paths = Rq3LegacyExportPipeline().export_kendall_tau()
    print("Generated Kendall Tau legacy artifacts:")
    for filename, path in sorted(output_paths.items()):
        print(f"- {filename}: {path}")


if __name__ == "__main__":
    main()
