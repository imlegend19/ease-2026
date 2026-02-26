"""CLI entrypoint for SANER-style fixed-issues RQ3 artifacts."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_legacy_exports import Rq3LegacyExportPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate fixed-issue outcome metrics and export SANER-style fixed "
            "pickle files for RQ3."
        ),
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild reverse-identity cache before running.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    IssueOutcomeMetricsPipeline().run(
        refresh_identity_cache=args.refresh_identity_cache,
        write_interim=True,
        write_csv=True,
    )
    legacy_paths = Rq3LegacyExportPipeline().export_legacy_issue_pickles(metric_names=("fixed",))

    print("Generated SANER-style fixed issue pickles:")
    for severity, hero_paths in legacy_paths["fixed"].items():
        print(f"- {severity}: {len(hero_paths)} files")


if __name__ == "__main__":
    main()
