"""CLI entrypoint for fixed/reopened issue outcome metrics."""


import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate fixed/reopened issue percentages by hero type and severity.",
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

    output_paths = IssueOutcomeMetricsPipeline().run(
        refresh_identity_cache=args.refresh_identity_cache,
        write_interim=True,
        write_csv=True,
    )
    print("Generated issue outcome artifacts:")
    print("- fixed pickles:")
    for severity, path in output_paths.fixed_pickles.items():
        print(f"  - {severity}: {path}")
    print("- reopened pickles:")
    for severity, path in output_paths.reopened_pickles.items():
        print(f"  - {severity}: {path}")


if __name__ == "__main__":
    main()

