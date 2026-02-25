"""CLI entrypoint for technical heroes based on commits."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.technical.commit_based import TechnicalCommitHeroPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate technical commit-based hero CSV and interim artifacts.",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild identity cache from MongoDB before running.",
    )
    parser.add_argument(
        "--no-interim",
        action="store_true",
        help="Skip writing interim pickle artifacts.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    pipeline = TechnicalCommitHeroPipeline()
    output_path = pipeline.run(
        refresh_identity_cache=args.refresh_identity_cache,
        write_interim=not args.no_interim,
    )
    print(f"Generated CSV: {output_path}")


if __name__ == "__main__":
    main()
