"""CLI entrypoint for SANER-style reopened-issues RQ3 artifacts."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.rq3_legacy_exports import Rq3LegacyExportPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate reopened-issue outcome metrics and export SANER-style reopened "
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
    legacy_paths = Rq3LegacyExportPipeline().export_legacy_issue_pickles(metric_names=("reopened",))

    print("Generated SANER-style reopened issue pickles:")
    for severity, hero_paths in legacy_paths["reopened"].items():
        print(f"- {severity}: {len(hero_paths)} files")


if __name__ == "__main__":
    main()
