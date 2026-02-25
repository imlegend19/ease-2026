"""CLI entrypoint for optional RQ3 Scott-Knott ESD rankings."""


import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_sk_esd import Rq3ScottKnottEsdPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RQ3 Scott-Knott ESD rankings (with mean fallback when R package is unavailable).",
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

    outputs = Rq3ScottKnottEsdPipeline().run_all()
    print("Generated RQ3 SK-ESD artifacts:")
    for metric, paths_by_severity in outputs.ranking_csv_paths.items():
        print(f"- {metric}:")
        for severity, path in paths_by_severity.items():
            print(f"  - {severity}: {path}")


if __name__ == "__main__":
    main()

