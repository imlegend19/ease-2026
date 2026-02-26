"""CLI entrypoint for SANER-style Scott-Knott ESD outputs."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_legacy_exports import Rq3LegacyExportPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Scott-Knott ESD outputs in SANER-compatible CSV format for "
            "fixed and reopened RQ3 metrics."
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
        help="Skip regenerating fixed/reopened issue metric artifacts.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


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

    output_paths, summary_path = Rq3LegacyExportPipeline().export_scott_knot_esd_rankings()

    print("Generated Scott-Knott ESD legacy artifacts:")
    print(f"- summary: {summary_path}")
    for metric_name, paths_by_severity in output_paths.items():
        print(f"- {metric_name}:")
        for severity, path in paths_by_severity.items():
            print(f"  - {severity}: {path}")


if __name__ == "__main__":
    main()
