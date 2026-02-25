"""CLI entrypoint to generate final_identity only."""

import argparse

from core.logging import setup_logging
from pipelines.preprocessing.derived_collections import DerivedCollectionsPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate only final_identity derived collection.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Append to existing collection instead of dropping it first.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    pipeline = DerivedCollectionsPipeline()
    stats = pipeline.build_final_identity(drop_existing=not args.keep_existing)
    print(f"Generated {stats.collection_name}: inserted={stats.inserted_count}")


if __name__ == "__main__":
    main()
