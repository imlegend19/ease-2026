"""CLI entrypoint for super heroes (social/technical intersections)."""

from __future__ import annotations

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.social.comment_based import SocialCommentHeroPipeline
from pipelines.social.issue_based import SocialIssueHeroPipeline
from pipelines.super.intersection_based import SuperIntersectionPipeline
from pipelines.technical.commit_based import TechnicalCommitHeroPipeline
from pipelines.technical.file_based import TechnicalFileHeroPipeline
from pipelines.technical.loc_based import TechnicalLocHeroPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate super-hero CSVs across all technical/social intersections.",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild identity cache from MongoDB before running.",
    )
    parser.add_argument(
        "--skip-prerequisites",
        action="store_true",
        help="Skip social/technical prerequisite pipelines and use existing interim artifacts.",
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

    if not args.skip_prerequisites:
        SocialCommentHeroPipeline().run(
            refresh_identity_cache=args.refresh_identity_cache,
            write_interim=True,
        )
        SocialIssueHeroPipeline().run(write_interim=True)
        TechnicalCommitHeroPipeline().run(write_interim=True)
        TechnicalLocHeroPipeline().run(write_interim=True)
        TechnicalFileHeroPipeline().run(write_interim=True)

    output_paths = SuperIntersectionPipeline().run_all()
    print("Generated CSV files:")
    for output_path in output_paths:
        print(f"- {output_path}")


if __name__ == "__main__":
    main()

