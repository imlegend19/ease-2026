"""CLI entrypoint for RQ3 ranking and Kendall Tau artifacts."""

from __future__ import annotations

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_rankings import Rq3RankingPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RQ3 ranking CSVs and Kendall Tau correlation matrices.",
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

    outputs = Rq3RankingPipeline().run_all()
    print("Generated RQ3 artifacts:")
    print(f"- fixed rankings: {outputs.fixed.mean_ranking_csv_path}")
    print(f"- fixed Kendall Tau: {outputs.fixed.kendall_tau_csv_path}")
    print(f"- reopened rankings: {outputs.reopened.mean_ranking_csv_path}")
    print(f"- reopened Kendall Tau: {outputs.reopened.kendall_tau_csv_path}")


if __name__ == "__main__":
    main()

