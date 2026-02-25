"""CLI entrypoint for resolution-time analysis artifacts."""


import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.resolution_time import ResolutionTimePipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate severity-wise assignee and hero average resolution-time artifacts.",
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

    output_paths = ResolutionTimePipeline().run(
        refresh_identity_cache=args.refresh_identity_cache,
        write_interim=True,
        write_csv=True,
    )
    print("Generated resolution-time artifacts:")
    for severity, path in output_paths.hero_csv_paths.items():
        print(f"- {severity}: {path}")


if __name__ == "__main__":
    main()

