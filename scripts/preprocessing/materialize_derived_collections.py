"""CLI entrypoint to materialize derived SmartSHARK collections."""

import argparse

from core.logging import setup_logging
from pipelines.preprocessing.derived_collections import DerivedCollectionsPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build derived collections required by hero pipelines: "
            "commit_with_project_info, comments_with_issue_and_project_info, final_identity."
        ),
    )
    parser.add_argument(
        "--step",
        choices=("all", "commit", "comments", "identity"),
        default="all",
        help="Which derived collection step to run.",
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
    drop_existing = not args.keep_existing

    if args.step == "all":
        stats = pipeline.run_all(drop_existing=drop_existing)
    elif args.step == "commit":
        stats = [pipeline.build_commit_with_project_info(drop_existing=drop_existing)]
    elif args.step == "comments":
        stats = [pipeline.build_comments_with_issue_and_project_info(drop_existing=drop_existing)]
    else:
        stats = [pipeline.build_final_identity(drop_existing=drop_existing)]

    print("Derived collection materialization complete:")
    for item in stats:
        print(f"- {item.collection_name}: inserted={item.inserted_count}")


if __name__ == "__main__":
    main()
